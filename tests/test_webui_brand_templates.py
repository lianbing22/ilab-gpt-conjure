"""Tests for BrandTemplateStore: immutability, versioning, content hashing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_image.branding.models import BrandTemplate, PlacementConfig, content_hash


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

    def test_legacy_recipe_defaults_scrim_policy_to_auto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            published = store.publish(_template())
            stored = json.loads(store.path.read_text(encoding="utf-8"))
            for layout in stored["versions"][0]["recipe"]["placements"].values():
                for placement in layout.values():
                    placement.pop("scrim_policy", None)
            store.path.write_text(json.dumps(stored), encoding="utf-8")

            reloaded = self._store(Path(tmp)).get_brand_template(published.template_id, published.version)

            self.assertEqual(reloaded.placements["square"]["logo"].scrim_policy, "auto")
            self.assertEqual(reloaded.placements["square"]["slogan"].scrim_policy, "auto")

    def test_v2_hash_matches_authoritative_stored_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            store.publish(_template(version=41, width_ratio_logo=0.16))
            v2 = store.publish(_template(version=99, width_ratio_logo=0.20))

            rebuilt = store.get_brand_template("metro-standard", 2)

            self.assertEqual(v2.version, 2)
            self.assertEqual(v2.recipe["version"], 2)
            self.assertEqual(rebuilt.version, 2)
            self.assertEqual(v2.content_hash, content_hash(rebuilt))

    def test_initialization_migrates_legacy_v2_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            store.publish(_template(width_ratio_logo=0.16))
            store.publish(_template(width_ratio_logo=0.20))
            stored_data = json.loads(store.path.read_text(encoding="utf-8"))
            legacy_hash = content_hash(_template(version=1, width_ratio_logo=0.20))
            stored_data["versions"][1]["content_hash"] = legacy_hash
            store.path.write_text(json.dumps(stored_data), encoding="utf-8")

            migrated_store = self._store(root)
            migrated = migrated_store.get("metro-standard", 2)
            rebuilt = migrated_store.get_brand_template("metro-standard", 2)

            self.assertNotEqual(migrated.content_hash, legacy_hash)
            self.assertEqual(migrated.content_hash, content_hash(rebuilt))

    def test_unchanged_recipe_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            first = store.publish(_template())
            second = store.publish(_template())

            self.assertEqual(first.version, second.version)
            self.assertEqual(first.content_hash, second.content_hash)

    def test_idempotency_ignores_caller_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            first = store.publish(_template(version=41))
            second = store.publish(_template(version=99))

            rebuilt = store.get_brand_template("metro-standard", 1)
            self.assertEqual(first.version, 1)
            self.assertEqual(second.version, 1)
            self.assertEqual(first.content_hash, content_hash(rebuilt))

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
