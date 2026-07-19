"""Immutable, versioned brand-template store.

A template describes *how* to overlay Logo + Slogan (placements, theme mode,
asset references). Templates are **append-only and immutable once published**:
editing a recipe publishes a new version rather than mutating the old one, so a
task record that cites ``template_id@version`` keeps rendering identically even
after the brand team ships a new look. Each version carries a ``content_hash``
over its recipe (via :func:`content_hash`) so callers can freeze and verify the
exact bytes used.

Persistence is a single JSON file (``templates.json``) rewritten atomically
under a lock. Version counts per template stay small, so a full rewrite is
cheap and keeps the format human-auditable.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from ..branding.models import BrandTemplate, content_hash
from .storage_utils import utc_now

TemplateStatus = Literal["active", "archived"]
LAYER_LAYOUTS = ("square", "portrait", "landscape")
LAYER_TONES = ("light-assets", "dark-assets")


@dataclass(frozen=True)
class BrandTemplateVersion:
    """A published, immutable template version plus bookkeeping."""

    template_id: str
    version: int
    name: str
    status: TemplateStatus
    content_hash: str
    created_at: str
    archived_at: str
    # The recipe itself, stored verbatim so content_hash stays verifiable.
    recipe: dict[str, Any]
    # Hashes emitted by the pre-authoritative-version publisher. Retained so
    # already-queued legacy tasks can recover across the one-time migration.
    legacy_content_hashes: tuple[str, ...] = field(default_factory=tuple)


def _recipe_from_brand_template(template: BrandTemplate) -> dict[str, Any]:
    """Serialize a BrandTemplate into a stable JSON-able recipe dict."""
    raw = asdict(template)
    return raw


def _recipes_equal_ignoring_version(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Compare template semantics while ignoring store-assigned versions."""
    return {key: value for key, value in left.items() if key != "version"} == {
        key: value for key, value in right.items() if key != "version"
    }


def _brand_template_from_recipe(recipe: dict[str, Any]) -> BrandTemplate:
    """Reconstruct a BrandTemplate from its stored recipe.

    JSON round-trips flatten the nested PlacementConfig dataclasses into plain
    dicts, so placements are re-hydrated into PlacementConfig objects (the
    compositor accesses them by attribute).
    """
    from ..branding.models import PlacementConfig

    raw_placements = recipe.get("placements", {})
    placements: dict[str, dict[str, PlacementConfig]] = {}
    for layout, elements in raw_placements.items():
        if not isinstance(elements, dict):
            continue
        placements[layout] = {
            element: PlacementConfig(
                anchor=str(cfg.get("anchor") or "top-left"),
                width_ratio=float(cfg.get("width_ratio") or 0.0),
                margin_x_ratio=float(cfg.get("margin_x_ratio") or 0.0),
                margin_y_ratio=float(cfg.get("margin_y_ratio") or 0.0),
                scrim_policy="never" if cfg.get("scrim_policy") == "never" else "auto",
            )
            for element, cfg in elements.items()
            if isinstance(cfg, dict)
        }
    return BrandTemplate(
        id=recipe["id"],
        version=recipe["version"],
        name=recipe["name"],
        theme_mode=recipe["theme_mode"],
        variant_policy=recipe["variant_policy"],
        placements=placements,  # type: ignore[arg-type]
        asset_variants=recipe.get("asset_variants", {}),
    )


def template_supports_layer(recipe: dict[str, Any], layer: str) -> bool:
    """Return whether a stored recipe can visibly render ``layer`` in every layout."""
    if layer not in {"logo", "slogan"}:
        return False
    variants = recipe.get("asset_variants")
    placements = recipe.get("placements")
    if not isinstance(variants, dict) or not isinstance(placements, dict):
        return False
    for tone in LAYER_TONES:
        tone_assets = variants.get(tone)
        if not isinstance(tone_assets, dict) or not str(tone_assets.get(layer) or "").strip():
            return False
    for layout in LAYER_LAYOUTS:
        layout_placements = placements.get(layout)
        placement = layout_placements.get(layer) if isinstance(layout_placements, dict) else None
        if not isinstance(placement, dict):
            return False
        try:
            if float(placement.get("width_ratio") or 0.0) <= 0:
                return False
        except (TypeError, ValueError):
            return False
    return True


class BrandTemplateStore:
    """Append-only, immutable-versioned template store backed by one JSON file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._migrate_legacy_content_hashes()

    # ------------------------------------------------------------- internals

    def _read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        versions = data.get("versions") if isinstance(data, dict) else None
        return versions if isinstance(versions, list) else []

    def _write_all(self, versions: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file + os.replace (same pattern as TaskStorage).
        import os
        import tempfile

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            ) as tmp:
                tmp_path = tmp.name
                tmp.write(json.dumps({"versions": versions}, ensure_ascii=False, indent=2))
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, self.path)
            tmp_path = None
        finally:
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink()
                except FileNotFoundError:
                    pass

    def _migrate_legacy_content_hashes(self) -> None:
        """Repair hashes written before recipes were stamped authoritatively."""
        with self._lock:
            versions = self._read_all()
            changed = False
            for record in versions:
                recipe = record.get("recipe") if isinstance(record, dict) else None
                if not isinstance(recipe, dict):
                    continue
                try:
                    header_version = int(record.get("version") or 0)
                    recipe_version = int(recipe.get("version") or 0)
                except (TypeError, ValueError):
                    continue
                if (
                    str(record.get("template_id") or "") != str(recipe.get("id") or "")
                    or header_version != recipe_version
                ):
                    # Identity drift is store corruption, not a legacy hash.
                    # Never re-sign the recipe under a different record header.
                    continue
                try:
                    authoritative_hash = content_hash(_brand_template_from_recipe(recipe))
                except Exception:
                    # Preserve existing read-time tolerance for malformed records.
                    continue
                if str(record.get("content_hash") or "") == authoritative_hash:
                    continue
                previous_hash = str(record.get("content_hash") or "").strip()
                legacy_hashes = [
                    str(value).strip()
                    for value in (record.get("legacy_content_hashes") or [])
                    if str(value).strip()
                ]
                if previous_hash and previous_hash not in legacy_hashes:
                    legacy_hashes.append(previous_hash)
                record["legacy_content_hashes"] = legacy_hashes
                record["content_hash"] = authoritative_hash
                changed = True
            if changed:
                try:
                    self._write_all(versions)
                except OSError:
                    # A read-only/corrupt store must not make initialization fail.
                    return

    @staticmethod
    def _to_record(v: dict[str, Any]) -> BrandTemplateVersion:
        return BrandTemplateVersion(
            template_id=str(v.get("template_id") or ""),
            version=int(v.get("version") or 0),
            name=str(v.get("name") or ""),
            status=v.get("status") or "active",  # type: ignore[assignment]
            content_hash=str(v.get("content_hash") or ""),
            created_at=str(v.get("created_at") or ""),
            archived_at=str(v.get("archived_at") or ""),
            recipe=v.get("recipe") if isinstance(v.get("recipe"), dict) else {},
            legacy_content_hashes=tuple(
                str(value).strip()
                for value in (v.get("legacy_content_hashes") or [])
                if str(value).strip()
            ),
        )

    # ------------------------------------------------------------------ read

    def list_versions(self, template_id: str) -> list[BrandTemplateVersion]:
        with self._lock:
            versions = self._read_all()
        return [self._to_record(v) for v in versions if str(v.get("template_id")) == template_id]

    def list_active(self) -> list[BrandTemplateVersion]:
        with self._lock:
            versions = self._read_all()
        # Latest active version per template_id.
        active: dict[str, BrandTemplateVersion] = {}
        for v in versions:
            if v.get("status") != "active":
                continue
            rec = self._to_record(v)
            existing = active.get(rec.template_id)
            if existing is None or rec.version > existing.version:
                active[rec.template_id] = rec
        return sorted(active.values(), key=lambda r: r.template_id)

    def get(self, template_id: str, version: int | None = None) -> BrandTemplateVersion:
        """Return a specific version, or the latest (any status) if omitted.

        Raises ``KeyError`` if the template/version does not exist.
        """
        with self._lock:
            versions = [self._to_record(v) for v in self._read_all() if str(v.get("template_id")) == template_id]
        if not versions:
            raise KeyError(template_id)
        if version is None:
            return max(versions, key=lambda r: r.version)
        for rec in versions:
            if rec.version == version:
                return rec
        raise KeyError(f"{template_id}@{version}")

    def get_brand_template(self, template_id: str, version: int | None = None) -> BrandTemplate:
        """Convenience: return the reconstructed :class:`BrandTemplate`."""
        record = self.get(template_id, version)
        template = _brand_template_from_recipe(record.recipe)
        if template.id != record.template_id or template.version != record.version:
            raise ValueError(
                "brand template identity mismatch: "
                f"record={record.template_id}@{record.version}, recipe={template.id}@{template.version}"
            )
        return template

    # ---------------------------------------------------------------- write

    def publish(self, template: BrandTemplate) -> BrandTemplateVersion:
        """Publish ``template`` as a new immutable version.

        The store assigns the authoritative next version for ``template.id``;
        the caller-provided version is ignored for semantic idempotency.
        ``content_hash`` is computed only after that authoritative version is
        stamped, so it always matches the stored recipe exactly.
        """
        incoming_recipe = _recipe_from_brand_template(template)

        with self._lock:
            versions = self._read_all()
            existing = [v for v in versions if str(v.get("template_id")) == template.id]

            # Version is store-owned metadata, so caller version changes alone
            # never publish a duplicate recipe.
            if existing:
                latest = max(existing, key=lambda v: int(v.get("version") or 0))
                latest_recipe = latest.get("recipe") if isinstance(latest.get("recipe"), dict) else {}
                if _recipes_equal_ignoring_version(latest_recipe, incoming_recipe):
                    return self._to_record(latest)

            next_version = max((int(v.get("version") or 0) for v in existing), default=0) + 1
            authoritative_template = replace(template, version=next_version)
            recipe = _recipe_from_brand_template(authoritative_template)
            recipe_hash = content_hash(authoritative_template)
            now = utc_now()
            record = {
                "template_id": template.id,
                "version": next_version,
                "name": template.name,
                "status": "active",
                "content_hash": recipe_hash,
                "created_at": now,
                "archived_at": "",
                "recipe": recipe,
            }
            # Publishing a new active version archives prior active versions of
            # the same template so list_active() stays one-per-template.
            for v in versions:
                if str(v.get("template_id")) == template.id and v.get("status") == "active":
                    v["status"] = "archived"
                    v["archived_at"] = now
            versions.append(record)
            self._write_all(versions)
            return self._to_record(record)

    def archive(self, template_id: str, version: int) -> BrandTemplateVersion:
        """Mark a specific version archived. Archived versions remain readable."""
        now = utc_now()
        with self._lock:
            versions = self._read_all()
            for v in versions:
                if str(v.get("template_id")) == template_id and int(v.get("version") or 0) == version:
                    v["status"] = "archived"
                    v["archived_at"] = now
                    self._write_all(versions)
                    return self._to_record(v)
        raise KeyError(f"{template_id}@{version}")
