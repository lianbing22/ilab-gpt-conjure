"""Tests for BrandTemplateStore: immutability, versioning, content hashing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_image.branding.models import BrandTemplate, PlacementConfig


def _template(
    id: str = "metro-standard",
    version: int = 1,
    name: str = "标准模板",
    width_ratio_logo: float = 0.16,
    margin: float = 0.035,
) -> BrandTemplate:
    placements = {
        layout: {
            "logo": PlacementConfig("top-left", width_ratio_logo, margin, margin),
            "slogan": PlacementConfig("bottom-right", 0.30, margin, margin),
        }
        for layout in ("square", "portrait", "landscape")
    }
    return BrandTemplate(
        id=id,
        version=version,
        name=name,
        theme_mode="auto",
        variant_policy="per-element",
        placements=placements,
        asset_variants={
            "light-assets": {"logo": "logo-light", "slogan": "slogan-light"},
            "dark-assets": {"logo": "logo-dark", "slogan": "slogan-dark"},
        },
    )


class BrandTemplateStoreTests(unittest.TestCase):
    def _store(self, root: Path):
        from codex_image.webui.brand_templates import BrandTemplateStore

        return BrandTemplateStore(root / "templates.json")

    def test_publish_assigns_version_1_for_new_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            rec = store.publish(_template())

            self.assertEqual(rec.version, 1)
            self.assertEqual(rec.status, "active")
            self.assertTrue(rec.content_hash)
            self.assertEqual(rec.template_id, "metro-standard")

    def test_changed_recipe_publishes_new_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            v1 = store.publish(_template(width_ratio_logo=0.16))
            v2 = store.publish(_template(width_ratio_logo=0.20))

            self.assertEqual(v1.version, 1)
            self.assertEqual(v2.version, 2)
            self.assertNotEqual(v1.content_hash, v2.content_hash)
            # v1 archived when v2 became active.
            self.assertEqual(store.get("metro-standard", 1).status, "archived")
            self.assertEqual(store.get("metro-standard", 2).status, "active")

    def test_unchanged_recipe_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            first = store.publish(_template())
            second = store.publish(_template())

            self.assertEqual(first.version, second.version)
            self.assertEqual(first.content_hash, second.content_hash)

    def test_published_version_is_immutable_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            original = _template()
            store.publish(original)

            reconstructed = store.get_brand_template("metro-standard", 1)

            self.assertEqual(reconstructed.id, original.id)
            self.assertEqual(reconstructed.theme_mode, original.theme_mode)
            self.assertEqual(
                reconstructed.placements["square"]["logo"].width_ratio,
                original.placements["square"]["logo"].width_ratio,
            )

    def test_list_active_returns_latest_per_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            store.publish(_template(id="a", width_ratio_logo=0.10))
            store.publish(_template(id="a", width_ratio_logo=0.14))  # v2 active
            store.publish(_template(id="b", width_ratio_logo=0.20))  # v1 active

            active = {r.template_id: r for r in store.list_active()}

            self.assertEqual(set(active), {"a", "b"})
            self.assertEqual(active["a"].version, 2)
            self.assertEqual(active["b"].version, 1)

    def test_get_latest_returns_highest_version_any_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            store.publish(_template(width_ratio_logo=0.10))
            store.publish(_template(width_ratio_logo=0.14))

            latest = store.get("metro-standard")  # version=None -> latest

            self.assertEqual(latest.version, 2)

    def test_archive_keeps_version_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            store.publish(_template(width_ratio_logo=0.10))
            store.publish(_template(width_ratio_logo=0.14))
            store.archive("metro-standard", 2)

            self.assertEqual(store.get("metro-standard", 2).status, "archived")
            self.assertEqual(store.get("metro-standard", 1).status, "archived")
            # No active version after archiving the latest.
            self.assertEqual([r for r in store.list_active() if r.template_id == "metro-standard"], [])

    def test_missing_template_raises_keyerror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            with self.assertRaises(KeyError):
                store.get("nonexistent")

    def test_content_hash_stable_across_reloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "templates.json"
            store_a = self._store(Path(tmp))
            rec = store_a.publish(_template())
            # New store instance reading the same file.
            store_b = self._store(Path(tmp))
            reloaded = store_b.get("metro-standard", 1)

            self.assertEqual(reloaded.content_hash, rec.content_hash)


if __name__ == "__main__":
    unittest.main()
