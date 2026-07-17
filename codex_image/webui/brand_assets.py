"""Content-addressed storage for brand overlay assets (Logo / Slogan PNGs).

Mirrors the sha256 content-addressing of :mod:`reference_files`, but with
image-specific validation (PNG magic, Pillow ``verify()``, a pixel-count cap to
reject decompression bombs, and a byte-size cap). Assets are immutable: the same
bytes always resolve to the same id, so a template that references an asset id
keeps rendering identically even after the uploader replaces a Gallery image of
the same name.

Storage layout::

    root/
      <id[:2]>/<id>.png      # the image bytes
      <id[:2]>/<id>.json     # metadata: original filename, mime, dims, hashes

The image is stored as-is (caller's bytes) plus a sidecar JSON record. Reads
return the record; the service layer opens the .png directly for compositing.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .storage_utils import _safe_filename, utc_now

# MVP: PNG only. WebP/SVG can be added later with their own validation.
ALLOWED_MIME_TYPES: dict[str, str] = {
    "image/png": ".png",
}
MAX_BRAND_ASSET_BYTES = 10 * 1024 * 1024  # 10 MB per asset
# Reject images whose decoded pixel area exceeds this (decompression bomb guard).
MAX_BRAND_ASSET_PIXELS = 50_000_000  # ~50 MP

_ASSET_ID_RE = re.compile(r"[0-9a-f]{64}")

# PNG magic bytes (the first 8 bytes of any PNG file).
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class BrandAsset:
    """A validated, stored brand asset record (no bytes — read from disk)."""

    id: str
    filename: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    sha256: str
    created_at: str
    last_used_at: str
    used_count: int


def validate_brand_asset(
    filename: str,
    data: bytes,
    content_type: str | None,
    *,
    max_bytes: int = MAX_BRAND_ASSET_BYTES,
    max_pixels: int = MAX_BRAND_ASSET_PIXELS,
) -> tuple[str, str, int, int]:
    """Validate a brand asset upload. Returns (asset_id, mime, width, height).

    Raises ``ValueError`` (with a stable code suffix) on any rejection so the
    route layer can map it to an HTTP 4xx without leaking internals.
    """
    if not data:
        raise ValueError("brand_asset_empty")
    if len(data) > max_bytes:
        raise ValueError("brand_asset_too_large")

    supplied_mime = str(content_type or "").split(";", 1)[0].strip().lower()
    # Trust magic bytes over the declared content-type, but if a content-type is
    # supplied it must at least be an image/* we accept.
    if supplied_mime and supplied_mime != "application/octet-stream" and supplied_mime not in ALLOWED_MIME_TYPES:
        raise ValueError("brand_asset_type_unsupported")

    # Magic-byte check first (cheap, catches non-images / renamed files).
    is_png = data.startswith(_PNG_MAGIC)
    if not is_png:
        raise ValueError("brand_asset_not_png")

    # Pillow verify() parses headers without fully decoding; catches truncated /
    # corrupt PNGs and enforces the pixel cap (Pillow raises DecompressionBomb).
    from PIL import Image  # local import keeps the module import-light

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()  # noqa: F841 — verify() only validates, does not load pixels
        # Re-open to read dimensions: verify() leaves the image unusable.
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
    except Exception as exc:  # PIL raises a variety of error types here
        raise ValueError("brand_asset_corrupt") from exc

    if width <= 0 or height <= 0:
        raise ValueError("brand_asset_corrupt")
    if width * height > max_pixels:
        raise ValueError("brand_asset_too_many_pixels")

    asset_id = hashlib.sha256(data).hexdigest()
    return asset_id, "image/png", width, height


class BrandAssetStorage:
    """Content-addressed store for brand overlay images."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ paths

    def _shard_dir(self, asset_id: str) -> Path:
        return self.root / asset_id[:2]

    def _image_path(self, asset_id: str) -> Path:
        return self._shard_dir(asset_id) / f"{asset_id}.png"

    def _meta_path(self, asset_id: str) -> Path:
        return self._shard_dir(asset_id) / f"{asset_id}.json"

    def _validate_id(self, asset_id: str) -> None:
        if not asset_id or not _ASSET_ID_RE.fullmatch(asset_id):
            raise ValueError("brand_asset_invalid_id")

    # ---------------------------------------------------------------- create

    def create_or_touch(
        self,
        filename: str,
        data: bytes,
        content_type: str | None,
    ) -> BrandAsset:
        """Store a validated asset, or touch it if identical bytes already exist.

        Returns the asset record. Identical content is idempotent: re-uploading
        the same Logo bumps ``used_count`` rather than creating a duplicate.
        """
        asset_id, mime, width, height = validate_brand_asset(filename, data, content_type)
        self._validate_id(asset_id)
        safe_name = _safe_filename(filename) or f"{asset_id}.png"
        now = utc_now()

        with self._lock:
            meta_path = self._meta_path(asset_id)
            image_path = self._image_path(asset_id)
            shard = self._shard_dir(asset_id)
            shard.mkdir(parents=True, exist_ok=True)

            if meta_path.exists():
                existing = self._read_meta(asset_id)
                record = {
                    **existing,
                    "last_used_at": now,
                    "used_count": int(existing.get("used_count", 0)) + 1,
                }
            else:
                # Write the image bytes exactly once for new content.
                image_path.write_bytes(data)
                record = {
                    "id": asset_id,
                    "filename": safe_name,
                    "mime_type": mime,
                    "width": width,
                    "height": height,
                    "size_bytes": len(data),
                    "sha256": asset_id,
                    "created_at": now,
                    "last_used_at": now,
                    "used_count": 1,
                }
            meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            return _record_to_asset(record)

    def touch(self, asset_id: str) -> BrandAsset:
        """Mark an existing asset as used again (bump last_used_at / used_count)."""
        self._validate_id(asset_id)
        with self._lock:
            record = self._read_meta(asset_id)
            record["last_used_at"] = utc_now()
            record["used_count"] = int(record.get("used_count", 0)) + 1
            self._meta_path(asset_id).write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return _record_to_asset(record)

    # ----------------------------------------------------------------- read

    def _read_meta(self, asset_id: str) -> dict[str, Any]:
        path = self._meta_path(asset_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(asset_id) from exc
        return data if isinstance(data, dict) else {}

    def get(self, asset_id: str) -> BrandAsset:
        self._validate_id(asset_id)
        return _record_to_asset(self._read_meta(asset_id))

    def image_path(self, asset_id: str) -> Path:
        """Return the on-disk image path, validating it stays under root.

        Guards against tampered metadata pointing outside the store (mirrors the
        reference-file safety check).
        """
        self._validate_id(asset_id)
        path = self._image_path(asset_id)
        try:
            path.resolve(strict=False).relative_to(self.root.resolve(strict=False))
        except ValueError as exc:
            raise FileNotFoundError(asset_id) from exc
        if not path.is_file():
            raise FileNotFoundError(asset_id)
        return path

    def list_recent(self, limit: int = 100) -> list[BrandAsset]:
        if not self.root.exists():
            return []
        records: list[dict[str, Any]] = []
        for meta_path in self.root.glob("*/*.json"):
            try:
                rec = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(rec, dict) and rec.get("id"):
                records.append(rec)
        records.sort(key=lambda r: str(r.get("last_used_at") or r.get("created_at") or ""), reverse=True)
        return [_record_to_asset(r) for r in records[:limit]]

    # --------------------------------------------------------------- delete

    def delete(self, asset_id: str) -> None:
        self._validate_id(asset_id)
        with self._lock:
            shard = self._shard_dir(asset_id)
            for path in (self._image_path(asset_id), self._meta_path(asset_id)):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            try:
                shard.rmdir()
            except OSError:
                pass


def _record_to_asset(record: dict[str, Any]) -> BrandAsset:
    return BrandAsset(
        id=str(record.get("id") or ""),
        filename=str(record.get("filename") or ""),
        mime_type=str(record.get("mime_type") or "image/png"),
        width=int(record.get("width") or 0),
        height=int(record.get("height") or 0),
        size_bytes=int(record.get("size_bytes") or 0),
        sha256=str(record.get("sha256") or record.get("id") or ""),
        created_at=str(record.get("created_at") or ""),
        last_used_at=str(record.get("last_used_at") or ""),
        used_count=int(record.get("used_count") or 0),
    )
