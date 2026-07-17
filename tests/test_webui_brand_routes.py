"""End-to-end tests for brand routes: asset upload, template publish, download."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image


def _rgba_png(size=(200, 80), color=(20, 20, 20, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _solid_png(size=(512, 512), color=(245, 245, 245)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _FakeClient:
    """Minimal image client stub (brand tests don't generate)."""

    def __init__(self, *_, **__):
        pass


class BrandRouteTests(unittest.TestCase):
    def _app(self, tmp: Path) -> TestClient:
        from codex_image.webui.app import create_app

        app = create_app(
            output_root=tmp / "tasks",
            gallery_root=tmp / "gallery",
            client_factory=lambda: _FakeClient(),
            auth_checker=lambda: True,
        )
        return TestClient(app)

    def test_upload_asset_then_list_and_fetch_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = self._app(Path(tmp))
            created = client.post(
                "/api/brand/assets",
                data={"filename": "logo.png"},
                files={"image": ("logo.png", _rgba_png(), "image/png")},
            )
            self.assertEqual(created.status_code, 200)
            asset = created.json()["asset"]
            self.assertEqual(asset["width"], 200)

            listed = client.get("/api/brand/assets").json()["items"]
            self.assertEqual(len(listed), 1)

            image_response = client.get(f"/api/brand/assets/{asset['id']}/image")
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response.headers["content-type"], "image/png")

    def test_upload_rejects_non_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = self._app(Path(tmp))
            response = client.post(
                "/api/brand/assets",
                data={"filename": "fake.png"},
                files={"image": ("fake.png", b"not a png", "image/png")},
            )
            self.assertEqual(response.status_code, 400)

    def test_publish_template_and_list_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = self._app(Path(tmp))
            # Upload the four assets first.
            ids = {}
            for element in ("logo", "slogan"):
                for tone, color in (("light-assets", (245, 245, 245, 255)), ("dark-assets", (20, 20, 20, 255))):
                    resp = client.post(
                        "/api/brand/assets",
                        data={"filename": f"{element}-{tone}.png"},
                        files={"image": (f"{element}-{tone}.png", _rgba_png(color=color), "image/png")},
                    )
                    ids[(tone, element)] = resp.json()["asset"]["id"]

            payload = {
                "id": "metro",
                "name": "Metro standard",
                "theme_mode": "auto",
                "variant_policy": "per-element",
                "placements": {
                    layout: {
                        "logo": {"anchor": "top-left", "width_ratio": 0.16, "margin_x_ratio": 0.035, "margin_y_ratio": 0.035},
                        "slogan": {"anchor": "bottom-right", "width_ratio": 0.30, "margin_x_ratio": 0.035, "margin_y_ratio": 0.035},
                    }
                    for layout in ("square", "portrait", "landscape")
                },
                "asset_variants": {
                    "light-assets": {"logo": ids[("light-assets", "logo")], "slogan": ids[("light-assets", "slogan")]},
                    "dark-assets": {"logo": ids[("dark-assets", "logo")], "slogan": ids[("dark-assets", "slogan")]},
                },
            }
            published = client.post("/api/brand/templates", json=payload).json()["template"]
            self.assertEqual(published["version"], 1)
            self.assertTrue(published["content_hash"])

            active = client.get("/api/brand/templates").json()["templates"]
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["template_id"], "metro")

            history = client.get("/api/brand/templates/metro").json()["versions"]
            self.assertEqual(len(history), 1)

    def test_download_branded_output_returns_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = self._app(Path(tmp))
            app_ctx = client.app.state.ctx
            storage = app_ctx.storage

            # Seed a completed task with a raw output.
            task = storage.create_task("generate")
            from codex_image.webui.storage import TaskStorage  # noqa: F401

            raw_path = storage.write_output(task.task_id, _solid_png(), "png", index=1)
            rel = storage.output_file(raw_path)
            outputs = [{"index": 1, "status": "completed", "file": rel, "url": f"/outputs/{rel}", "size": "512x512"}]
            storage.update_metadata(
                task.task_id,
                lambda m: m.update({"task_id": task.task_id, "status": "completed", "params": {}, "outputs": outputs}),
            )

            # Upload assets + publish template.
            ids = {}
            for element in ("logo", "slogan"):
                for tone, color in (("light-assets", (245, 245, 245, 255)), ("dark-assets", (20, 20, 20, 255))):
                    resp = client.post(
                        "/api/brand/assets",
                        data={"filename": f"{element}-{tone}.png"},
                        files={"image": (f"{element}-{tone}.png", _rgba_png(color=color), "image/png")},
                    )
                    ids[(tone, element)] = resp.json()["asset"]["id"]
            from codex_image.branding.models import BrandTemplate, PlacementConfig

            template = BrandTemplate(
                id="t1", version=1, name="t", theme_mode="auto", variant_policy="per-element",
                placements={l: {"logo": PlacementConfig("top-left", 0.16, 0.035, 0.035), "slogan": PlacementConfig("bottom-right", 0.30, 0.035, 0.035)} for l in ("square", "portrait", "landscape")},
                asset_variants={"light-assets": {"logo": ids[("light-assets", "logo")], "slogan": ids[("light-assets", "slogan")]}, "dark-assets": {"logo": ids[("dark-assets", "logo")], "slogan": ids[("dark-assets", "slogan")]}},
            )
            app_ctx.brand_template_store.publish(template)

            # Enable branding + recompose.
            storage.update_metadata(task.task_id, lambda m: m["params"].__setitem__("branding_request", {"enabled": True, "template_id": "t1", "template_version": 1}))
            outcome = client.post(f"/api/tasks/{task.task_id}/branding/recompose").json()
            self.assertEqual(outcome["status"], "completed")

            download = client.get(f"/api/tasks/{task.task_id}/outputs/1/branding/download")
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.headers["content-type"], "image/png")


if __name__ == "__main__":
    unittest.main()
