"""Tests for BrandingService: orchestration, idempotency, failure isolation."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Literal

from PIL import Image

from codex_image.branding.models import BrandTemplate, PlacementConfig, content_hash
from codex_image.branding.service import BrandingService


def _png(size=(512, 512), color=(245, 245, 245)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _rgba_png(size=(200, 80), color=(20, 20, 20, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _template(
    asset_ids: dict[str, dict[str, str]],
    *,
    template_id: str = "t1",
    theme_mode: Literal["auto", "light-assets", "dark-assets"] = "auto",
    variant_policy: Literal["per-element", "unified"] = "per-element",
) -> BrandTemplate:
    placements = {
        layout: {
            "logo": PlacementConfig("top-left", 0.16, 0.035, 0.035),
            "slogan": PlacementConfig("bottom-right", 0.30, 0.035, 0.035),
        }
        for layout in ("square", "portrait", "landscape")
    }
    return BrandTemplate(
        id=template_id,
        version=1,
        name="test",
        theme_mode=theme_mode,
        variant_policy=variant_policy,
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

    def _seed_brand_assets(self, asset_storage, *, prefix: str = "") -> dict[str, dict[str, str]]:
        light_logo = asset_storage.create_or_touch(f"{prefix}logo-light.png", _rgba_png((100, 60), (245, 245, 245, 255)), "image/png")
        dark_logo = asset_storage.create_or_touch(f"{prefix}logo-dark.png", _rgba_png((100, 60), (20, 20, 20, 255)), "image/png")
        light_slogan = asset_storage.create_or_touch(f"{prefix}slogan-light.png", _rgba_png((300, 60), (245, 245, 245, 255)), "image/png")
        dark_slogan = asset_storage.create_or_touch(f"{prefix}slogan-dark.png", _rgba_png((300, 60), (20, 20, 20, 255)), "image/png")
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

    def test_legacy_frozen_hash_rejects_tampered_same_version_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            version = template_store.publish(_template(ids))
            stored_data = json.loads(template_store.path.read_text(encoding="utf-8"))
            stored_data["versions"][0]["recipe"]["placements"]["square"]["logo"]["width_ratio"] = 0.99
            template_store.path.write_text(json.dumps(stored_data), encoding="utf-8")
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "template_id": version.template_id,
                    "template_version": version.version,
                    "template_content_hash": version.content_hash,
                },
            )

            outcome = service.apply_task_branding(task_id)

            metadata = storage.read_metadata(task_id)
            self.assertEqual(outcome.status, "failed")
            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["branding_status"], "failed")
            self.assertNotIn("branding", metadata["outputs"][0])

    def test_layers_logo_only_records_only_logo_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            version = template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "mode": "layers",
                    "layers": {
                        "logo": {
                            "template_id": "t1",
                            "template_version": version.version,
                            "template_content_hash": version.content_hash,
                        }
                    },
                },
            )

            outcome = service.apply_task_branding(task_id)

            self.assertEqual(outcome.status, "completed")
            branding = storage.read_metadata(task_id)["outputs"][0]["branding"]
            self.assertEqual(branding["mode"], "layers")
            self.assertIn("logo", branding["layers"])
            self.assertNotIn("slogan", branding["layers"])
            self.assertEqual(set(branding["asset_tones"].keys()), {"logo"})

    def test_layers_slogan_only_records_only_slogan_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            version = template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "mode": "layers",
                    "layers": {
                        "slogan": {
                            "template_id": "t1",
                            "template_version": version.version,
                            "template_content_hash": version.content_hash,
                        }
                    },
                },
            )

            outcome = service.apply_task_branding(task_id)

            self.assertEqual(outcome.status, "completed")
            branding = storage.read_metadata(task_id)["outputs"][0]["branding"]
            self.assertEqual(set(branding["layers"].keys()), {"slogan"})
            self.assertEqual(set(branding["asset_tones"].keys()), {"slogan"})

    def test_layers_can_mix_logo_and_slogan_from_different_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            logo_ids = self._seed_brand_assets(asset_storage, prefix="logo-template-")
            slogan_ids = self._seed_brand_assets(asset_storage, prefix="slogan-template-")
            logo_version = template_store.publish(_template(logo_ids, template_id="logo-t"))
            slogan_version = template_store.publish(_template(slogan_ids, template_id="slogan-t"))
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "mode": "layers",
                    "layers": {
                        "logo": {
                            "template_id": "logo-t",
                            "template_version": logo_version.version,
                            "template_content_hash": logo_version.content_hash,
                        },
                        "slogan": {
                            "template_id": "slogan-t",
                            "template_version": slogan_version.version,
                            "template_content_hash": slogan_version.content_hash,
                        },
                    },
                },
            )

            outcome = service.apply_task_branding(task_id)

            self.assertEqual(outcome.status, "completed")
            branding = storage.read_metadata(task_id)["outputs"][0]["branding"]
            self.assertEqual(branding["layers"]["logo"]["template_id"], "logo-t")
            self.assertEqual(branding["layers"]["slogan"]["template_id"], "slogan-t")
            self.assertTrue(branding["template_id"].startswith("layers:"))

    def test_layer_hash_mismatch_fails_without_touching_generation_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            version = template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "mode": "layers",
                    "layers": {
                        "logo": {
                            "template_id": "t1",
                            "template_version": version.version,
                            "template_content_hash": "not-the-stored-hash",
                        }
                    },
                },
            )

            outcome = service.apply_task_branding(task_id)

            metadata = storage.read_metadata(task_id)
            self.assertEqual(outcome.status, "failed")
            self.assertEqual(outcome.failed_count, 1)
            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["branding_status"], "failed")
            self.assertEqual(metadata["branding_error"], "branding_template_missing")
            self.assertNotIn("branding", metadata["outputs"][0])

    def test_incompatible_layer_recipe_fails_even_with_correct_hash(self) -> None:
        cases = (
            {"template_id": "forced", "theme_mode": "dark-assets"},
            {"template_id": "unified", "variant_policy": "unified"},
        )
        for case in cases:
            with self.subTest(template_id=case["template_id"]), tempfile.TemporaryDirectory() as tmp:
                storage, asset_storage, template_store, service = self._setup(Path(tmp))
                ids = self._seed_brand_assets(asset_storage)
                version = template_store.publish(_template(ids, **case))  # type: ignore[arg-type]
                task_id = self._seed_completed_task(
                    storage,
                    branding_request={
                        "enabled": True,
                        "mode": "layers",
                        "layers": {
                            "logo": {
                                "template_id": version.template_id,
                                "template_version": version.version,
                                "template_content_hash": version.content_hash,
                            }
                        },
                    },
                )

                outcome = service.apply_task_branding(task_id)

                metadata = storage.read_metadata(task_id)
                self.assertEqual(outcome.status, "failed")
                self.assertEqual(metadata["status"], "completed")
                self.assertEqual(metadata["branding_status"], "failed")
                self.assertNotIn("branding", metadata["outputs"][0])

    def test_tampered_layer_recipe_fails_when_record_and_frozen_hash_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            version = template_store.publish(_template(ids))
            stored_data = json.loads(template_store.path.read_text(encoding="utf-8"))
            stored_data["versions"][0]["recipe"]["placements"]["square"]["logo"]["width_ratio"] = 0.99
            template_store.path.write_text(json.dumps(stored_data), encoding="utf-8")
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "mode": "layers",
                    "layers": {
                        "logo": {
                            "template_id": version.template_id,
                            "template_version": version.version,
                            "template_content_hash": version.content_hash,
                        }
                    },
                },
            )

            outcome = service.apply_task_branding(task_id)

            metadata = storage.read_metadata(task_id)
            self.assertEqual(outcome.status, "failed")
            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["branding_status"], "failed")
            self.assertNotIn("branding", metadata["outputs"][0])

    def test_migrated_legacy_v2_hash_allows_layer_compositing(self) -> None:
        from codex_image.webui.brand_templates import BrandTemplateStore

        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, _ = self._setup(Path(tmp))
            v1_ids = self._seed_brand_assets(asset_storage, prefix="v1-")
            v2_ids = self._seed_brand_assets(asset_storage, prefix="v2-")
            template_store.publish(_template(v1_ids))
            v2_template = replace(_template(v2_ids), name="test v2")
            template_store.publish(v2_template)
            stored_data = json.loads(template_store.path.read_text(encoding="utf-8"))
            legacy_hash = content_hash(v2_template)
            stored_data["versions"][1]["content_hash"] = legacy_hash
            template_store.path.write_text(json.dumps(stored_data), encoding="utf-8")

            migrated_store = BrandTemplateStore(template_store.path)
            migrated = migrated_store.get("t1", 2)
            service = BrandingService(storage, asset_storage, migrated_store)
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "mode": "layers",
                    "layers": {
                        "logo": {
                            "template_id": migrated.template_id,
                            "template_version": migrated.version,
                            "template_content_hash": migrated.content_hash,
                        }
                    },
                },
            )

            outcome = service.apply_task_branding(task_id)

            metadata = storage.read_metadata(task_id)
            self.assertNotEqual(migrated.content_hash, legacy_hash)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(metadata["branding_status"], "completed")
            self.assertEqual(metadata["outputs"][0]["branding"]["status"], "completed")

    def test_pre_migration_legacy_frozen_hash_survives_store_migration(self) -> None:
        from codex_image.webui.brand_templates import BrandTemplateStore

        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, _ = self._setup(Path(tmp))
            v1_ids = self._seed_brand_assets(asset_storage, prefix="legacy-v1-")
            v2_ids = self._seed_brand_assets(asset_storage, prefix="legacy-v2-")
            template_store.publish(_template(v1_ids))
            v2_input = replace(_template(v2_ids), name="legacy v2")
            template_store.publish(v2_input)
            legacy_hash = content_hash(v2_input)
            stored_data = json.loads(template_store.path.read_text(encoding="utf-8"))
            stored_data["versions"][1]["content_hash"] = legacy_hash
            template_store.path.write_text(json.dumps(stored_data), encoding="utf-8")
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "template_id": "t1",
                    "template_version": 2,
                    "template_content_hash": legacy_hash,
                },
            )

            migrated_store = BrandTemplateStore(template_store.path)
            migrated = migrated_store.get("t1", 2)
            service = BrandingService(storage, asset_storage, migrated_store)
            outcome = service.apply_task_branding(task_id)

            metadata = storage.read_metadata(task_id)
            self.assertIn(legacy_hash, migrated.legacy_content_hashes)
            self.assertNotEqual(migrated.content_hash, legacy_hash)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(metadata["branding_status"], "completed")
            self.assertEqual(metadata["outputs"][0]["branding"]["status"], "completed")

    def test_layer_rejects_record_recipe_identity_drift_without_resigning(self) -> None:
        from codex_image.webui.brand_templates import BrandTemplateStore

        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, _ = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            version = template_store.publish(_template(ids))
            stored_data = json.loads(template_store.path.read_text(encoding="utf-8"))
            original_hash = stored_data["versions"][0]["content_hash"]
            stored_data["versions"][0]["recipe"]["id"] = "different-template"
            template_store.path.write_text(json.dumps(stored_data), encoding="utf-8")

            migrated_store = BrandTemplateStore(template_store.path)
            migrated = migrated_store.get(version.template_id, version.version)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                migrated_store.get_brand_template(version.template_id, version.version)
            service = BrandingService(storage, asset_storage, migrated_store)
            task_id = self._seed_completed_task(
                storage,
                branding_request={
                    "enabled": True,
                    "mode": "layers",
                    "layers": {
                        "logo": {
                            "template_id": version.template_id,
                            "template_version": version.version,
                            "template_content_hash": original_hash,
                        }
                    },
                },
            )

            outcome = service.apply_task_branding(task_id)

            metadata = storage.read_metadata(task_id)
            self.assertEqual(migrated.content_hash, original_hash)
            self.assertEqual(outcome.status, "failed")
            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["branding_status"], "failed")
            self.assertEqual(metadata["branding_error"], "branding_template_missing")
            self.assertNotIn("branding", metadata["outputs"][0])

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

    def test_recovery_resumes_interrupted_branding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            template_store.publish(_template(ids))
            task_id = self._seed_completed_task(
                storage,
                branding_request={"enabled": True, "template_id": "t1", "template_version": 1},
            )
            # Simulate a crash mid-branding: status stuck at running, no output.branding yet.
            storage.update_metadata(task_id, lambda m: m.__setitem__("branding_status", "running"))

            recovered = service.recover_interrupted_branding()

            self.assertEqual(recovered, 1)
            metadata = storage.read_metadata(task_id)
            self.assertEqual(metadata["branding_status"], "completed")
            self.assertEqual(metadata["outputs"][0]["branding"]["status"], "completed")

    def test_recovery_skips_completed_and_disabled_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage, asset_storage, template_store, service = self._setup(Path(tmp))
            ids = self._seed_brand_assets(asset_storage)
            template_store.publish(_template(ids))
            # Completed-branding task + a disabled task.
            completed_id = self._seed_completed_task(
                storage,
                branding_request={"enabled": True, "template_id": "t1", "template_version": 1},
            )
            service.apply_task_branding(completed_id)
            disabled_id = self._seed_completed_task(storage, branding_request=None)

            recovered = service.recover_interrupted_branding()

            self.assertEqual(recovered, 0)


if __name__ == "__main__":
    unittest.main()
