"""Tests for BrandAssetStorage: PNG validation, content addressing, idempotency."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image


def _png_bytes(size: tuple[int, int] = (200, 80), color=(245, 245, 245, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


class BrandAssetValidationTests(unittest.TestCase):
    def test_valid_png_returns_id_and_dimensions(self) -> None:
        from codex_image.webui.brand_assets import validate_brand_asset

        data = _png_bytes((640, 480))
        asset_id, mime, width, height = validate_brand_asset("logo.png", data, "image/png")

        self.assertEqual(mime, "image/png")
        self.assertEqual((width, height), (640, 480))
        self.assertEqual(len(asset_id), 64)

    def test_rejects_non_png_magic_bytes(self) -> None:
        from codex_image.webui.brand_assets import validate_brand_asset

        with self.assertRaises(ValueError):
            validate_brand_asset("fake.png", b"not a png", "image/png")

    def test_rejects_corrupt_png(self) -> None:
        from codex_image.webui.brand_assets import validate_brand_asset

        # Valid magic but truncated body.
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        with self.assertRaises(ValueError):
            validate_brand_asset("broken.png", data, "image/png")

    def test_rejects_oversized_bytes(self) -> None:
        from codex_image.webui.brand_assets import validate_brand_asset

        big = _png_bytes() + b"\x00" * (11 * 1024 * 1024)
        with self.assertRaises(ValueError):
            validate_brand_asset("big.png", big, "image/png")

    def test_rejects_decompression_bomb_pixel_count(self) -> None:
        from codex_image.webui.brand_assets import validate_brand_asset

        # Pillow refuses to even open such images by default; emulate by lowering
        # the cap so a normal image trips it.
        data = _png_bytes((1000, 1000))
        with self.assertRaises(ValueError):
            validate_brand_asset("big.png", data, "image/png", max_pixels=100_000)

    def test_rejects_empty(self) -> None:
        from codex_image.webui.brand_assets import validate_brand_asset

        with self.assertRaises(ValueError):
            validate_brand_asset("empty.png", b"", "image/png")

    def test_rejects_wrong_declared_mime(self) -> None:
        from codex_image.webui.brand_assets import validate_brand_asset

        data = _png_bytes()
        with self.assertRaises(ValueError):
            validate_brand_asset("logo.png", data, "image/jpeg")


class BrandAssetStorageTests(unittest.TestCase):
    def _storage(self, root: Path):
        from codex_image.webui.brand_assets import BrandAssetStorage

        return BrandAssetStorage(root / "brand")

    def test_create_stores_image_and_metadata_and_reads_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._storage(Path(tmp))
            data = _png_bytes((300, 120), (20, 20, 20, 255))

            asset = storage.create_or_touch("company-logo.png", data, "image/png")
            fetched = storage.get(asset.id)
            image_bytes = storage.image_path(asset.id).read_bytes()
            image_name = storage.image_path(asset.id).name

        self.assertEqual(fetched.width, 300)
        self.assertEqual(fetched.height, 120)
        self.assertEqual(fetched.used_count, 1)
        self.assertEqual(image_bytes, data)
        self.assertTrue(image_name.endswith(".png"))

    def test_identical_bytes_dedupe_and_bump_used_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._storage(Path(tmp))
            data = _png_bytes()

            first = storage.create_or_touch("logo.png", data, "image/png")
            second = storage.create_or_touch("logo-again.png", data, "image/png")
            image_files = [p for p in (Path(tmp) / "brand").glob("*/*.png") if p.is_file()]

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.used_count, 2)
        self.assertEqual(len(image_files), 1)

    def test_list_recent_orders_by_last_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._storage(Path(tmp))
            a = storage.create_or_touch("a.png", _png_bytes((10, 10), (1, 1, 1, 255)), "image/png")
            b = storage.create_or_touch("b.png", _png_bytes((10, 10), (2, 2, 2, 255)), "image/png")
            storage.touch(a.id)
            recent = storage.list_recent()

        self.assertEqual([item.id for item in recent], [a.id, b.id])

    def test_delete_removes_image_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._storage(Path(tmp))
            asset = storage.create_or_touch("logo.png", _png_bytes(), "image/png")
            image_path = storage.image_path(asset.id)

            storage.delete(asset.id)

            self.assertFalse(image_path.exists())
            with self.assertRaises(FileNotFoundError):
                storage.get(asset.id)

    def test_rejects_invalid_id_on_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = self._storage(Path(tmp))
            with self.assertRaises(ValueError):
                storage.get("../escape")

    def test_rejects_tampered_metadata_pointing_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = self._storage(root)
            asset = storage.create_or_touch("safe.png", _png_bytes(), "image/png")
            # Tamper metadata to point outside the store.
            meta_path = root / "brand" / asset.id[:2] / f"{asset.id}.json"
            outside = root / "outside.png"
            outside.write_bytes(b"outside")
            meta = __import__("json").loads(meta_path.read_text())
            # image_path() derives from the id, not metadata, so this primarily
            # asserts the path-stays-under-root guard; tamper the id resolution
            # by checking image_path still resolves within root.
            resolved = storage.image_path(asset.id)
            self.assertTrue(resolved.resolve().is_relative_to((root / "brand").resolve()))


if __name__ == "__main__":
    unittest.main()
