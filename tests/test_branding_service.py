"""Tests for BrandingService: orchestration, idempotency, failure isolation."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from codex_image.branding.models import BrandTemplate, PlacementConfig
from codex_image.branding.service import BrandingService


def _png(size=(512, 512), color=(245, 245, 245)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _rgba_png(size=(200, 80), color=(20, 20, 20, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _template(asset_ids: dict[str, dict[str, str]]) -> BrandTemplate:
    placements = {
        layout: {
            "logo": PlacementConfig("top-left", 0.16, 0.035, 0.035),
            "slogan": PlacementConfig("bottom-right", 0.30, 0.035, 0.035),
        }
        for layout in ("square", "portrait", "landscape")
    }
    return BrandTemplate(
        id="t1",
        version=1,
        name="test",
        theme_mode="auto",
        variant_policy="per-element",
        placements=placements,
        asset_variants=asset_ids,
    )


class BrandingServiceTests(unittest.TestCase):
    def _setup(self, tmp: Path):
        from codex_image.webui.brand_assets import BrandAssetStorage
        from codex_image.webui.brand_templates import BrandTemplateStore
        from codex_image.webui.storage import TaskStorage

        storage = TaskStorage(
            input_root=tmp / "inputs",
            output_root=tmp / "outputs",
            source_data_root=tmp / "outputs" / "source-data",
        )
        asset_storage = BrandAssetStorage(tmp / "brand-assets")
        template_store = BrandTemplateStore(tmp / "templates.json")
        service = BrandingService(storage, asset_storage, template_store)
        return storage, asset_storage, template_store, service

    def _seed_brand_assets(self, asset_storage) -> dict[str, dict[str, str]]:
        light_logo = asset_storage.create_or_touch("logo-light.png", _rgba_png((100, 60), (245, 245, 245, 255)), "image/png")
        dark_logo = asset_storage.create_or_touch("logo-dark.png", _rgba_png((100, 60), (20, 20, 20, 255)), "image/png")
        light_slogan = asset_storage.create_or_touch("slogan-light.png", _rgba_png((300, 60), (245, 245, 245, 255)), "image/png")
        dark_slogan = asset_storage.create_or_touch("slogan-dark.png", _rgba_png((300, 60), (20, 20, 20, 255)), "image/png")
        return {
            "light-assets": {"logo": light_logo.id, "slogan": light_slogan.id},
            "dark-assets": {"logo": dark_logo.id, "slogan": dark_slogan.id},
        }

    def _seed_completed_task(self, storage, *, branding_request, raw_color=(245, 245, 245), n=1) -> str:
        task = storage.create_task("generate")
        outputs = []
        for i in range(1, n + 1):
            path = storage.write_output(task.task_id, _png((512, 512), raw_color), "png", index=i)
            rel = storage.output_file(path)
            outputs.append({"index": i, "status": "completed", "file": rel, "url": f"/outputs/{rel}", "size": "512x512"})
        params = {"n": n}
        if branding_request is not None:
            params["branding_request"] = branding_request
        storage.update_metadata(task.task_id, lambda m: m.update({
            "task_id": task.task_id,
            "status": "completed",
            "params": params,
            "outputs": outputs,
            "output_files": [o["file"] for o in outputs],
        }))
        return task.task_id

    def test_disabled_when_no_branding_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, service = self._setup(Path(tmp))
            task_id = self._seed_completed_task(service.storage, branding_request=None)
            outcome = service.apply_task_branding(task_id)
            self.assertEqual(outcome.status, "disabled")
            self.assertEqual(outcome.branded_count, 0)

    def test_completes_and_writes_branded_derivative_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={"enabled": True, "template_id": "t1", "template_version": 1},
            )

            outcome = service.apply_task_branding(task_id)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(outcome.branded_count, 1)

            metadata = storage.read_metadata(task_id)
            branding = metadata["outputs"][0]["branding"]
            self.assertEqual(branding["status"], "completed")
            self.assertTrue(branding["request_hash"])
            branded_path = storage.output_path(branding["file"])
            self.assertTrue(branded_path.is_file())
            self.assertEqual(metadata["branding_status"], "completed")

    def test_idempotent_second_run_skips_recompositing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={"enabled": True, "template_id": "t1", "template_version": 1},
            )

            service.apply_task_branding(task_id)
            meta1 = storage.read_metadata(task_id)
            hash1 = meta1["outputs"][0]["branding"]["request_hash"]
            mtime1 = storage.output_path(meta1["outputs"][0]["branding"]["file"]).stat().st_mtime_ns

            # Second run must not rewrite the branded file (same hash, same mtime).
            service.apply_task_branding(task_id)
            meta2 = storage.read_metadata(task_id)
            hash2 = meta2["outputs"][0]["branding"]["request_hash"]
            mtime2 = storage.output_path(meta2["outputs"][0]["branding"]["file"]).stat().st_mtime_ns

            self.assertEqual(hash1, hash2)
            self.assertEqual(mtime1, mtime2)

    def test_failure_isolation_one_bad_output_partial_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={"enabled": True, "template_id": "t1", "template_version": 1},
                n=2,
            )
            # Corrupt one raw output's file reference so compositing raises.
            storage.update_metadata(task_id, lambda m: m["outputs"][0].__setitem__("file", "missing.png"))

            outcome = service.apply_task_branding(task_id)

            self.assertEqual(outcome.status, "partial_failed")
            self.assertEqual(outcome.branded_count, 1)
            self.assertEqual(outcome.failed_count, 1)
            # Generation task status untouched.
            self.assertEqual(storage.read_metadata(task_id)["status"], "completed")

    def test_missing_template_marks_failed_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            task_id = self._seed_completed_task(
                storage,
                branding_request={"enabled": True, "template_id": "nope", "template_version": 1},
            )

            outcome = service.apply_task_branding(task_id)
            self.assertEqual(outcome.status, "failed")
            self.assertEqual(storage.read_metadata(task_id)["branding_status"], "failed")

    def test_does_not_touch_raw_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={"enabled": True, "template_id": "t1", "template_version": 1},
            )
            raw_rel = storage.read_metadata(task_id)["outputs"][0]["file"]
            raw_path = storage.output_path(raw_rel)
            raw_bytes_before = raw_path.read_bytes()
            raw_mtime = raw_path.stat().st_mtime_ns

            service.apply_task_branding(task_id)

            self.assertEqual(raw_path.read_bytes(), raw_bytes_before)
            self.assertEqual(raw_path.stat().st_mtime_ns, raw_mtime)


if __name__ == "__main__":
    unittest.main()
