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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..branding.models import BrandTemplate, content_hash
from .storage_utils import utc_now

TemplateStatus = Literal["active", "archived"]


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


def _recipe_from_brand_template(template: BrandTemplate) -> dict[str, Any]:
    """Serialize a BrandTemplate into a stable JSON-able recipe dict."""
    raw = asdict(template)
    return raw


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


class BrandTemplateStore:
    """Append-only, immutable-versioned template store backed by one JSON file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

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
        return _brand_template_from_recipe(self.get(template_id, version).recipe)

    # ---------------------------------------------------------------- write

    def publish(self, template: BrandTemplate) -> BrandTemplateVersion:
        """Publish ``template`` as a new immutable version.

        The incoming ``template.version`` is treated as a *floor*: the store
        assigns the next version number for ``template.id`` (existing versions
        are never overwritten). ``content_hash`` is computed from the recipe so
        callers can verify the exact bytes later.
        """
        recipe = _recipe_from_brand_template(template)
        recipe_hash = content_hash(template)
        now = utc_now()

        with self._lock:
            versions = self._read_all()
            existing = [v for v in versions if str(v.get("template_id")) == template.id]
            next_version = (max((int(v.get("version") or 0) for v in existing), default=0) + 1) if existing else 1

            # If the latest version has identical content, return it idempotently
            # instead of creating a duplicate.
            if existing:
                latest = max(existing, key=lambda v: int(v.get("version") or 0))
                if latest.get("content_hash") == recipe_hash:
                    return self._to_record(latest)

            # Stamp the recipe with the authoritative version before hashing is
            # already done; keep the stored recipe's version in sync with the
            # assigned version so reconstruction round-trips.
            recipe = {**recipe, "version": next_version}
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
