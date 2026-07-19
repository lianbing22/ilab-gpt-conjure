#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codex_image.branding.models import BrandTemplate, PlacementConfig
from codex_image.webui.brand_assets import BrandAssetStorage
from codex_image.webui.brand_templates import BrandTemplateStore
from codex_image.webui.schemas import DEFAULT_WEBUI_SETTINGS_PATH
from codex_image.webui.settings_store import WebUISettings


BRAND_PACKAGES = {
    "hengtai-default": ("恒泰母品牌", "hengtai-h-color.png", "hengtai-h-inverted.png"),
    "hengtai-life": ("恒泰生活", "life-h-color.png", "life-h-inverted.png"),
    "hengtai-service": ("恒泰服务", "service-h-color.png", "service-h-inverted.png"),
    "hengtai-tech": ("恒泰技术", "tech-h-color.png", "tech-h-inverted.png"),
}


def _placements() -> dict[str, dict[str, PlacementConfig]]:
    elements = {
        "logo": PlacementConfig(
            anchor="top-left",
            width_ratio=0.18,
            margin_x_ratio=0.04,
            margin_y_ratio=0.04,
            scrim_policy="never",
        ),
        "slogan": PlacementConfig(
            anchor="bottom-center",
            width_ratio=0.35,
            margin_x_ratio=0.0,
            margin_y_ratio=0.02,
            scrim_policy="auto",
        ),
    }
    return {layout: dict(elements) for layout in ("square", "portrait", "landscape")}


def _store_asset(storage: BrandAssetStorage, path: Path) -> str:
    asset = storage.create_or_touch(path.name, path.read_bytes(), "image/png")
    return asset.id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register the official Hengtai brand assets and publish selectable overlay packages."
    )
    parser.add_argument("--settings", type=Path, default=DEFAULT_WEBUI_SETTINGS_PATH)
    parser.add_argument("--assets-root", type=Path, default=REPO_ROOT / "assets" / "hengtai-brand")
    parser.add_argument("--source-data-root", type=Path, default=None)
    args = parser.parse_args()

    source_data_root = args.source_data_root or WebUISettings(args.settings).read_paths()["source_data_root"]
    asset_storage = BrandAssetStorage(source_data_root / "brand-assets")
    template_store = BrandTemplateStore(source_data_root / "brand-templates.json")

    assets_root = args.assets_root.resolve()
    footer_dark = _store_asset(asset_storage, assets_root / "slogan-footer-dark.png")
    footer_light = _store_asset(asset_storage, assets_root / "slogan-footer-light.png")

    assets: dict[str, str] = {
        "slogan-footer-dark.png": footer_dark,
        "slogan-footer-light.png": footer_light,
    }
    templates: list[dict[str, object]] = []
    for template_id, (name, color_filename, inverted_filename) in BRAND_PACKAGES.items():
        color_id = _store_asset(asset_storage, assets_root / "logos" / color_filename)
        inverted_id = _store_asset(asset_storage, assets_root / "logos" / inverted_filename)
        assets[color_filename] = color_id
        assets[inverted_filename] = inverted_id
        version = template_store.publish(
            BrandTemplate(
                id=template_id,
                version=1,
                name=name,
                theme_mode="auto",
                variant_policy="per-element",
                placements=_placements(),
                asset_variants={
                    "dark-assets": {"logo": color_id, "slogan": footer_dark},
                    "light-assets": {"logo": inverted_id, "slogan": footer_light},
                },
            )
        )
        templates.append(
            {
                "template_id": version.template_id,
                "version": version.version,
                "name": version.name,
                "content_hash": version.content_hash,
            }
        )

    print(
        json.dumps(
            {
                "source_data_root": str(source_data_root),
                "assets": assets,
                "templates": templates,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
