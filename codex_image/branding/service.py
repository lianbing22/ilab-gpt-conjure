"""Brand-overlay post-processing service.

Runs after a generation task completes successfully. For each completed raw
output it composites the Logo + Slogan from the task's frozen brand request
(using :func:`compose_with_assets` so each image gets the tone-matching asset),
writes a branded derivative file, and records per-output ``branding`` state plus
a task-level ``branding_status``.

Key properties (from the approved v3 plan):

* **Failure isolation**: a branding error never flips the generation task to
  failed. ``apply_task_branding`` catches per-output exceptions and records
  ``branding_status = failed`` (or ``partial_failed``); the caller (queue
  runtime) wraps the whole call in its own try/except too.
* **Idempotency**: each output's ``branding.request_hash`` gates recomposition;
  an existing branded file with a matching hash is skipped.
* **Immutability of raw outputs**: the raw image file is read-only; branded
  files use the ``{task_id}-brand-{index}-{hash[:12]}.png`` naming.
* **No asset guessing**: assets come from the frozen template snapshot's
  ``asset_variants``; the service resolves both tone variants from
  ``BrandAssetStorage`` and lets the sampler pick per element.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PIL import Image

from ..webui.brand_assets import BrandAssetStorage
from ..webui.brand_templates import BrandTemplateStore, template_supports_layer
from ..webui.storage import TaskStorage
from ..webui.storage_utils import utc_now
from .compositor import COMPOSITOR_VERSION, compose_with_assets, compute_request_hash
from .models import BrandTemplate, content_hash

logger = logging.getLogger(__name__)

# Branded thumbnail long edge, matching the raw thumbnail cap for visual parity.
_BRAND_THUMBNAIL_MAX = 768


@dataclass
class BrandingOutcome:
    """Aggregate result of branding one task."""

    task_id: str
    status: str  # disabled | completed | partial_failed | failed | skipped
    branded_count: int
    failed_count: int
    total: int


class BrandingService:
    """Orchestrates brand compositing for completed generation tasks."""

    def __init__(
        self,
        storage: TaskStorage,
        asset_storage: BrandAssetStorage,
        template_store: BrandTemplateStore,
    ) -> None:
        self.storage = storage
        self.asset_storage = asset_storage
        self.template_store = template_store

    # ------------------------------------------------------------------ entry

    def apply_task_branding(self, task_id: str) -> BrandingOutcome:
        """Composite branded outputs for ``task_id`` if branding is enabled.

        Safe to call on any task: returns ``status="disabled"`` / ``"skipped"``
        when branding isn't requested or the task has no completed outputs, and
        never raises (all errors are captured per output and aggregated).
        """
        try:
            metadata = self.storage.read_metadata(task_id)
        except FileNotFoundError:
            return BrandingOutcome(task_id, "skipped", 0, 0, 0)

        params = metadata.get("params") if isinstance(metadata.get("params"), dict) else {}
        branding_request = params.get("branding_request") if isinstance(params.get("branding_request"), dict) else None
        if not branding_request or not branding_request.get("enabled"):
            return BrandingOutcome(task_id, "disabled", 0, 0, 0)

        # Only brand successfully generated outputs.
        outputs = [o for o in _completed_outputs(metadata)]
        if not outputs:
            return BrandingOutcome(task_id, "skipped", 0, 0, 0)

        try:
            template, branding_sources = self._resolve_branding_template(branding_request)
        except (KeyError, ValueError, TypeError, FileNotFoundError):
            self._record_task_status(task_id, metadata, "failed", error="branding_template_missing")
            return BrandingOutcome(task_id, "failed", 0, len(outputs), len(outputs))

        # Set running up-front so observers can see progress (and recovery can
        # detect an interrupted run).
        self._record_task_status(task_id, metadata, "running")
        metadata = self.storage.read_metadata(task_id)

        branded = 0
        failed = 0
        per_output_results: list[tuple[int, dict[str, Any] | None]] = []
        for output in outputs:
            index = _positive_int(output.get("index")) or 0
            try:
                branding_record = self._brand_one(task_id, metadata, output, template, branding_sources)
                per_output_results.append((index, branding_record))
                branded += 1
            except Exception as exc:  # never let one output abort the rest
                logger.exception("branding failed for task %s output %s", task_id, index)
                per_output_results.append((index, {"status": "failed", "error": str(exc)}))
                failed += 1

        # Write per-output branding under the task lock, merged onto freshest metadata.
        def _merge(m: dict[str, Any]) -> None:
            outs = m.get("outputs") if isinstance(m.get("outputs"), list) else []
            for idx, rec in per_output_results:
                for o in outs:
                    if _positive_int(o.get("index")) == idx and isinstance(o, dict):
                        o["branding"] = rec
                        break

        self.storage.update_metadata(task_id, _merge)

        if failed == 0:
            status = "completed"
        elif branded == 0:
            status = "failed"
        else:
            status = "partial_failed"
        self._record_task_status(task_id, None, status)
        return BrandingOutcome(task_id, status, branded, failed, len(outputs))

    # --------------------------------------------------------- per-output

    def _brand_one(
        self,
        task_id: str,
        metadata: dict[str, Any],
        output: dict[str, Any],
        template: BrandTemplate,
        branding_sources: dict[str, Any],
    ) -> dict[str, Any]:
        """Composite one raw output. Returns the branding record to store."""
        raw_path = self._resolve_raw_path(output)
        if raw_path is None or not raw_path.is_file():
            raise FileNotFoundError("raw output missing")

        assets = self._load_asset_variants(template)
        request_hash = self._request_hash(raw_path, template, assets)

        # Idempotency: if this output already has a completed branding with the
        # same hash and the file still exists, skip recompositing entirely.
        existing = output.get("branding") if isinstance(output.get("branding"), dict) else None
        if (
            existing
            and existing.get("status") == "completed"
            and existing.get("request_hash") == request_hash
        ):
            existing_path = self.storage.output_path(str(existing.get("file") or ""))
            if existing_path.is_file():
                return existing

        with Image.open(raw_path) as raw:
            raw.load()
            composed, report = compose_with_assets(raw, assets=assets, template=template)

        # Flatten to RGB PNG for portable branded output.
        out_buf = io.BytesIO()
        composed.convert("RGB").save(out_buf, format="PNG")
        composed_bytes = out_buf.getvalue()

        branded_path = self.storage.write_branded_output(
            task_id, composed_bytes, index=_positive_int(output.get("index")) or 1, request_hash=request_hash
        )
        branded_rel = self.storage.output_file(branded_path)
        thumbnail_rel = self._write_branded_thumbnail(task_id, output, composed_bytes, request_hash)

        elements = report.get("elements") if isinstance(report.get("elements"), dict) else {}
        asset_tones = {
            element: (elements.get(element) or {}).get("chosen_tone")
            for element in ("logo", "slogan")
            if element in elements
        }
        enabled_layers = list(asset_tones.keys())

        record = {
            "status": "completed",
            "file": branded_rel,
            "url": f"/outputs/{branded_rel}",
            "thumbnail_file": thumbnail_rel,
            "thumbnail_url": f"/outputs/{thumbnail_rel}" if thumbnail_rel else "",
            "template_id": template.id,
            "template_version": template.version,
            "request_hash": request_hash,
            "compositor_version": COMPOSITOR_VERSION,
            "asset_tones": asset_tones,
            "layout": report.get("layout"),
            "completed_at": utc_now(),
            "error": None,
        }
        if branding_sources.get("mode") == "layers":
            record["mode"] = "layers"
            record["layers"] = {
                element: branding_sources["layers"][element]
                for element in enabled_layers
                if element in branding_sources.get("layers", {})
            }
        return record

    # ------------------------------------------------------------- helpers

    def _resolve_branding_template(self, branding_request: dict[str, Any]) -> tuple[BrandTemplate, dict[str, Any]]:
        """Resolve a frozen legacy or layer request into one internal template."""
        if branding_request.get("mode") == "layers":
            return self._resolve_layer_template(branding_request)

        template_version = branding_request.get("template_version")
        template_id = str(branding_request.get("template_id") or "")
        stored_version = self.template_store.get(
            template_id,
            int(template_version) if template_version is not None else None,
        )
        template = self.template_store.get_brand_template(stored_version.template_id, stored_version.version)
        if content_hash(template) != stored_version.content_hash:
            raise ValueError(
                f"stored brand template content hash mismatch: {stored_version.template_id}@{stored_version.version}"
            )
        frozen_hash = str(branding_request.get("template_content_hash") or "").strip()
        accepted_hashes = {stored_version.content_hash, *stored_version.legacy_content_hashes}
        if stored_version.version != 1:
            # Old publish() hashed the caller's template before stamping the
            # store-owned version. All published customer templates originated
            # at v1, so retain that deterministic recovery path for stores that
            # were migrated before legacy hashes started being recorded.
            accepted_hashes.add(content_hash(replace(template, version=1)))
        if frozen_hash and frozen_hash not in accepted_hashes:
            raise ValueError(
                f"brand template content hash mismatch: {stored_version.template_id}@{stored_version.version}"
            )
        return template, {"mode": "legacy"}

    def _resolve_layer_template(self, branding_request: dict[str, Any]) -> tuple[BrandTemplate, dict[str, Any]]:
        layers = branding_request.get("layers") if isinstance(branding_request.get("layers"), dict) else {}
        selected: dict[str, tuple[BrandTemplate, str]] = {}
        for element in ("logo", "slogan"):
            layer = layers.get(element)
            if not isinstance(layer, dict):
                continue
            template_id = str(layer.get("template_id") or "").strip()
            if not template_id:
                continue
            version = layer.get("template_version")
            if version is None:
                raise ValueError(f"brand template version missing: {template_id}")
            frozen_hash = str(layer.get("template_content_hash") or "").strip()
            if not frozen_hash:
                raise ValueError(f"brand template content hash missing: {template_id}@{version}")
            stored_version = self.template_store.get(template_id, int(version))
            if stored_version.content_hash != frozen_hash:
                raise ValueError(f"brand template content hash mismatch: {template_id}@{version}")
            if (
                stored_version.recipe.get("theme_mode") != "auto"
                or stored_version.recipe.get("variant_policy") != "per-element"
            ):
                raise ValueError(f"brand template is incompatible with layered branding: {template_id}@{version}")
            if not template_supports_layer(stored_version.recipe, element):
                raise ValueError(f"brand template does not provide a complete {element} layer: {template_id}@{version}")
            template = self.template_store.get_brand_template(
                stored_version.template_id,
                stored_version.version,
            )
            if content_hash(template) != stored_version.content_hash:
                raise ValueError(f"stored brand template content hash mismatch: {template_id}@{version}")
            selected[element] = (template, stored_version.content_hash)
        if not selected:
            raise KeyError("no branding layers")

        placements: dict[str, dict[str, Any]] = {}
        asset_variants: dict[str, dict[str, str]] = {"light-assets": {}, "dark-assets": {}}
        sources: dict[str, dict[str, Any]] = {}
        id_parts: list[str] = []
        for element in ("logo", "slogan"):
            if element not in selected:
                continue
            source_template, stored_hash = selected[element]
            id_parts.append(f"{element}:{source_template.id}@{source_template.version}")
            sources[element] = {
                "template_id": source_template.id,
                "template_version": source_template.version,
                "template_content_hash": stored_hash,
            }
            for layout, source_placements in source_template.placements.items():
                if element not in source_placements:
                    continue
                placements.setdefault(layout, {})[element] = source_placements[element]
            for tone in ("light-assets", "dark-assets"):
                tone_assets = source_template.asset_variants.get(tone) or {}  # type: ignore[call-overload]
                asset_id = str(tone_assets.get(element) or "")
                if not asset_id:
                    raise FileNotFoundError(f"brand asset missing: {tone}/{element}")
                asset_variants[tone][element] = asset_id

        template = BrandTemplate(
            id="layers:" + "|".join(id_parts),
            version=1,
            name="Layered branding",
            theme_mode="auto",
            variant_policy="per-element",
            placements=placements,  # type: ignore[arg-type]
            asset_variants=asset_variants,  # type: ignore[arg-type]
        )
        return template, {"mode": "layers", "layers": sources}

    def _resolve_raw_path(self, output: dict[str, Any]) -> Path | None:
        filename = str(output.get("file") or "").strip()
        if not filename and output.get("url"):
            filename = str(output["url"]).removeprefix("/outputs/").lstrip("/")
        if not filename:
            return None
        path = self.storage.output_path(filename)
        root = self.storage.output_root.resolve(strict=False)
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError:
            return None
        # Only read genuine raw outputs ({task_id}-image-...), never branded files.
        if "-image-" not in path.name:
            return None
        return path

    def _load_asset_variants(self, template: BrandTemplate) -> dict[str, dict[str, Image.Image]]:
        """Load both tone variants (light/dark) for enabled overlay elements."""
        variants = template.asset_variants or {}
        enabled_elements = [element for element in ("logo", "slogan") if any(element in p for p in template.placements.values())]
        if not enabled_elements:
            raise FileNotFoundError("brand placement missing")
        assets: dict[str, dict[str, Image.Image]] = {}
        for tone in ("light-assets", "dark-assets"):
            ids = variants.get(tone) or {}  # type: ignore[call-overload]
            element_images: dict[str, Image.Image] = {}
            for element in enabled_elements:
                asset_id = str(ids.get(element) or "")
                if not asset_id:
                    raise FileNotFoundError(f"brand asset missing: {tone}/{element}")
                path = self.asset_storage.image_path(asset_id)
                with Image.open(path) as img:
                    img.load()
                    element_images[element] = img.copy()
            assets[tone] = element_images
        return assets

    def _request_hash(
        self,
        raw_path: Path,
        template: BrandTemplate,
        assets: dict[str, dict[str, Image.Image]],
    ) -> str:
        raw_bytes = raw_path.read_bytes()
        logo = (assets.get("dark-assets") or {}).get("logo")
        slogan = (assets.get("dark-assets") or {}).get("slogan")
        logo_bytes = _image_to_png_bytes(logo) if logo is not None else None
        slogan_bytes = _image_to_png_bytes(slogan) if slogan is not None else None
        return compute_request_hash(raw_bytes, template, logo_bytes, slogan_bytes)

    def _write_branded_thumbnail(
        self,
        task_id: str,
        output: dict[str, Any],
        composed_bytes: bytes,
        request_hash: str,
    ) -> str:
        index = _positive_int(output.get("index")) or 1
        short_hash = (request_hash or "")[:12] or "unhashed"
        thumb_dir = self.storage.output_root / "thumbnails" / _task_date_dir(self.storage, task_id)
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / f"{task_id}-brand-{index}-{short_hash}-thumb.jpg"
        try:
            with Image.open(io.BytesIO(composed_bytes)) as img:
                img.thumbnail((_BRAND_THUMBNAIL_MAX, _BRAND_THUMBNAIL_MAX), Image.Resampling.LANCZOS)
                img.convert("RGB").save(thumb_path, format="JPEG", quality=88)
        except Exception:
            logger.exception("branded thumbnail failed for task %s output %s", task_id, index)
            return ""
        return self.storage.output_file(thumb_path)

    def _record_task_status(self, task_id: str, metadata: dict[str, Any] | None, status: str, *, error: str = None) -> None:
        def _apply(m: dict[str, Any]) -> None:
            m["branding_status"] = status
            m["branding_updated_at"] = utc_now()
            if error is not None:
                m["branding_error"] = error
            elif status in ("completed", "running"):
                m.pop("branding_error", None)

        self.storage.update_metadata(task_id, _apply)

    # ----------------------------------------------------------- recovery

    def recover_interrupted_branding(self, *, limit: int = 500) -> int:
        """Resume branding for tasks left in pending/running by a crash.

        Scans task metadata for tasks with branding enabled but an incomplete
        branding_status, resets them, and re-applies idempotent compositing.
        Safe to call at startup (single-threaded) and re-runnable. Returns the
        number of tasks reprocessed.
        """
        reprocessed = 0
        for metadata_path in self.storage.iter_metadata_paths()[:limit]:
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(metadata, dict):
                continue
            task_id = str(metadata.get("task_id") or metadata_path.name.removesuffix(".metadata.json"))
            params = metadata.get("params") if isinstance(metadata.get("params"), dict) else {}
            branding_request = params.get("branding_request") if isinstance(params.get("branding_request"), dict) else None
            status = str(metadata.get("branding_status") or "")
            if not branding_request or not branding_request.get("enabled"):
                continue
            if status not in ("pending", "running"):
                continue
            # Reset and re-run. apply_task_branding is idempotent, so already-
            # written branded files (matching hash) are preserved.
            self._record_task_status(task_id, None, "pending")
            try:
                self.apply_task_branding(task_id)
                reprocessed += 1
            except Exception:
                logger.exception("branding recovery failed for task %s", task_id)
        return reprocessed


def _completed_outputs(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    outs = metadata.get("outputs") if isinstance(metadata.get("outputs"), list) else []
    return [o for o in outs if isinstance(o, dict) and o.get("status") == "completed" and o.get("file")]


def _positive_int(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _image_to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGBA").save(buf, format="PNG")
    return buf.getvalue()


def _task_date_dir(storage: TaskStorage, task_id: str) -> str:
    # Mirror storage_utils._task_date_directory without the private import dance.
    from ..webui.storage_utils import _task_date_directory

    return _task_date_directory(task_id)
