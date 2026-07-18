from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from codex_image.branding.compositor import compose_with_assets
from codex_image.webui.brand_assets import BrandAssetStorage
from codex_image.webui.brand_templates import BrandTemplateStore


ROOT = Path(__file__).resolve().parents[1]


def _register(source_data_root: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "register-hengtai-brand.py"),
            "--source-data-root",
            str(source_data_root),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_registration_is_idempotent_and_publishes_four_customer_choices(tmp_path: Path) -> None:
    first = _register(tmp_path)
    second = _register(tmp_path)

    assert len(first["assets"]) == 10
    assert [item["template_id"] for item in first["templates"]] == [
        "hengtai-default",
        "hengtai-life",
        "hengtai-service",
        "hengtai-tech",
    ]
    assert [(item["template_id"], item["version"]) for item in first["templates"]] == [
        (item["template_id"], item["version"]) for item in second["templates"]
    ]


def test_default_package_places_exact_assets_at_vi_positions(tmp_path: Path) -> None:
    _register(tmp_path)
    asset_storage = BrandAssetStorage(tmp_path / "brand-assets")
    template = BrandTemplateStore(tmp_path / "brand-templates.json").get_brand_template("hengtai-default")

    assert template.placements["square"]["logo"].anchor == "top-left"
    assert template.placements["square"]["logo"].width_ratio == 0.18
    assert template.placements["square"]["slogan"].anchor == "bottom-center"
    assert template.placements["square"]["slogan"].width_ratio == 0.35

    assets = {}
    for tone, ids in template.asset_variants.items():
        assets[tone] = {}
        for element, asset_id in ids.items():
            with Image.open(asset_storage.image_path(asset_id)) as image:
                image.load()
                assets[tone][element] = image.copy()

    canvas = Image.new("RGB", (1000, 1000), "white")
    branded, report = compose_with_assets(canvas, assets=assets, template=template)
    logo_box = report["elements"]["logo"]["box"]
    slogan_box = report["elements"]["slogan"]["box"]

    assert logo_box[0] == 40
    assert logo_box[1] == 40
    assert slogan_box[0] == (1000 - slogan_box[2]) // 2
    assert slogan_box[1] + slogan_box[3] == 980
    assert branded.convert("RGB").tobytes() != canvas.tobytes()


def test_frontend_exposes_brand_material_picker_and_submits_selected_template() -> None:
    html = (ROOT / "codex_image/webui/static/index.html").read_text(encoding="utf-8")
    module = (ROOT / "codex_image/webui/frontend/src/brand-materials.ts").read_text(encoding="utf-8")
    submit = (ROOT / "codex_image/webui/frontend/src/task-submit.ts").read_text(encoding="utf-8")
    styles = (ROOT / "codex_image/webui/static/styles/50-image-input-gallery.css").read_text(encoding="utf-8")
    responsive = (ROOT / "codex_image/webui/static/styles/80-utilities-responsive.css").read_text(encoding="utf-8")

    assert 'id="brandMaterialPicker"' in html
    assert 'id="brandMaterialList"' in html
    assert 'fetch("/api/brand/templates")' in module
    assert 'role="radio"' in module
    assert 'form.append("branding_template_id", state.selectedBrandingTemplateId)' in submit
    assert ".brand-material-option.active" in styles
    assert "scroll-snap-type: x proximity" in responsive
