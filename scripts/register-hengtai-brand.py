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


DEFAULT_SLOGAN = {
    "color": "slogan-footer-dark.png",
    "inverted": "slogan-footer-light.png",
}

LOGO_PACKAGES = (
    ("hengtai-default", "恒泰母品牌｜横版", "logos/hengtai-h-color.png", "logos/hengtai-h-inverted.png", 0.18),
    ("hengtai-default-vertical", "恒泰母品牌｜竖版", "logos/hengtai-v-color.png", "logos/hengtai-v-inverted.png", 0.14),
    (
        "hengtai-combined-brands-horizontal",
        "恒泰生活·服务·技术｜联用横版",
        "logos/combined-brands-h-color.png",
        "logos/combined-brands-h-inverted.png",
        0.18,
    ),
    ("hengtai-life", "恒泰生活｜横版", "logos/life-h-color.png", "logos/life-h-inverted.png", 0.18),
    ("hengtai-life-vertical", "恒泰生活｜竖版", "logos/life-v-color.png", "logos/life-v-inverted.png", 0.14),
    ("hengtai-service", "恒泰服务｜横版", "logos/service-h-color.png", "logos/service-h-inverted.png", 0.18),
    (
        "hengtai-service-vertical",
        "恒泰服务｜竖版",
        "logos/service-v-color.png",
        "logos/service-v-inverted.png",
        0.14,
    ),
    (
        "hengtai-service-tod-horizontal",
        "恒泰服务·TOD｜横版",
        "logos/service-tod-h-color.png",
        "logos/service-tod-h-inverted.png",
        0.18,
    ),
    (
        "hengtai-service-tod-vertical",
        "恒泰服务·TOD｜竖版",
        "logos/service-tod-v-color.png",
        "logos/service-tod-v-inverted.png",
        0.14,
    ),
    (
        "hengtai-service-residential-horizontal",
        "恒泰服务·住宅｜横版",
        "logos/service-residential-h-color.png",
        "logos/service-residential-h-inverted.png",
        0.18,
    ),
    (
        "hengtai-service-commercial-horizontal",
        "恒泰服务·商业｜横版",
        "logos/service-commercial-h-color.png",
        "logos/service-commercial-h-inverted.png",
        0.18,
    ),
    ("hengtai-tech", "恒泰技术｜横版", "logos/tech-h-color.png", "logos/tech-h-inverted.png", 0.18),
    ("hengtai-tech-vertical", "恒泰技术｜竖版", "logos/tech-v-color.png", "logos/tech-v-inverted.png", 0.14),
    ("hengtai-pr-vertical", "P+R 停车换乘｜竖版", "logos/pr-v-color.png", "logos/pr-v-inverted.png", 0.14),
    (
        "hengtai-atai-home-horizontal",
        "阿泰家｜横版",
        "logos/atai-home-h-color.png",
        "logos/atai-home-h-inverted.png",
        0.18,
    ),
    ("hengtai-atai-home-vertical", "阿泰家｜竖版", "logos/atai-home-v-color.png", "logos/atai-home-v-inverted.png", 0.14),
    (
        "xiamen-metro-residential-horizontal",
        "厦门地铁住宅物业｜横版",
        "logos/metro-residential-h-color.png",
        "logos/metro-residential-h-inverted.png",
        0.18,
    ),
    (
        "xiamen-metro-residential-vertical",
        "厦门地铁住宅物业｜竖版",
        "logos/metro-residential-v-color.png",
        "logos/metro-residential-v-inverted.png",
        0.14,
    ),
    (
        "xiamen-metro-commercial-horizontal",
        "厦门地铁商业物业｜横版",
        "logos/metro-commercial-h-color.png",
        "logos/metro-commercial-h-inverted.png",
        0.18,
    ),
    (
        "xiamen-metro-commercial-vertical",
        "厦门地铁商业物业｜竖版",
        "logos/metro-commercial-v-color.png",
        "logos/metro-commercial-v-inverted.png",
        0.14,
    ),
)

SLOGAN_PACKAGES = (
    (
        "hengtai-slogan-mission",
        "您的需求就是我们的目标",
        "logos/hengtai-h-color.png",
        "logos/hengtai-h-inverted.png",
        "slogans/hengtai-mission-color.png",
        "slogans/hengtai-mission-inverted.png",
    ),
    (
        "hengtai-slogan-tod",
        "您的幸福就是我们的目标｜恒泰服务·TOD",
        "logos/service-tod-h-color.png",
        "logos/service-tod-h-inverted.png",
        "slogans/tod-mission-color.png",
        "slogans/tod-mission-inverted.png",
    ),
)


def _placements(logo_width_ratio: float) -> dict[str, dict[str, PlacementConfig]]:
    elements = {
        "logo": PlacementConfig(
            anchor="top-left",
            width_ratio=logo_width_ratio,
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
    assets: dict[str, str] = {}

    def asset_id(relative_path: str) -> str:
        if relative_path not in assets:
            assets[relative_path] = _store_asset(asset_storage, assets_root / relative_path)
        return assets[relative_path]

    footer_color = asset_id(DEFAULT_SLOGAN["color"])
    footer_inverted = asset_id(DEFAULT_SLOGAN["inverted"])
    packages = [
        (
            template_id,
            name,
            color_path,
            inverted_path,
            DEFAULT_SLOGAN["color"],
            DEFAULT_SLOGAN["inverted"],
            logo_width,
        )
        for template_id, name, color_path, inverted_path, logo_width in LOGO_PACKAGES
    ]
    packages.extend(
        (
            template_id,
            name,
            logo_color_path,
            logo_inverted_path,
            slogan_color_path,
            slogan_inverted_path,
            0.18,
        )
        for (
            template_id,
            name,
            logo_color_path,
            logo_inverted_path,
            slogan_color_path,
            slogan_inverted_path,
        ) in SLOGAN_PACKAGES
    )

    templates: list[dict[str, object]] = []
    for (
        template_id,
        name,
        logo_color_path,
        logo_inverted_path,
        slogan_color_path,
        slogan_inverted_path,
        logo_width,
    ) in packages:
        color_logo = asset_id(logo_color_path)
        inverted_logo = asset_id(logo_inverted_path)
        color_slogan = footer_color if slogan_color_path == DEFAULT_SLOGAN["color"] else asset_id(slogan_color_path)
        inverted_slogan = (
            footer_inverted
            if slogan_inverted_path == DEFAULT_SLOGAN["inverted"]
            else asset_id(slogan_inverted_path)
        )
        version = template_store.publish(
            BrandTemplate(
                id=template_id,
                version=1,
                name=name,
                theme_mode="auto",
                variant_policy="per-element",
                placements=_placements(logo_width),
                asset_variants={
                    "dark-assets": {"logo": color_logo, "slogan": color_slogan},
                    "light-assets": {"logo": inverted_logo, "slogan": inverted_slogan},
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
