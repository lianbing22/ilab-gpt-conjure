from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
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


def test_frontend_exposes_independent_brand_layers_and_new_submit_fields() -> None:
    html = (ROOT / "codex_image/webui/static/index.html").read_text(encoding="utf-8")
    module = (ROOT / "codex_image/webui/frontend/src/brand-materials.ts").read_text(encoding="utf-8")
    submit = (ROOT / "codex_image/webui/frontend/src/task-submit.ts").read_text(encoding="utf-8")
    redesign = (ROOT / "codex_image/webui/static/styles/85-ui-redesign.css").read_text(encoding="utf-8")

    assert 'id="brandMaterialPicker"' in html
    assert 'id="brandMaterialList"' in html
    assert 'id="brandMaterialDrawer"' in html
    assert 'data-i18n-attr="aria-label:brand.layers"' in html
    assert 'id="brandMaterialDrawerTitle"' in html
    assert 'id="brandMaterialSearch"' in html
    assert 'id="brandMaterialDrawerConfirm"' in html
    assert 'data-brand-layer-toggle="${layer}"' in module
    assert 'data-brand-layer-open="${layer}"' in module
    assert 'aria-controls="brandMaterialDrawer"' in module
    assert 'aria-expanded="${drawerExpanded ? "true" : "false"}"' in module
    assert 'fetch("/api/brand/templates")' in module
    assert 'const BRAND_LAYERS: BrandLayer[] = ["logo", "slogan"]' in module
    assert "templateSupportsLayer(template, layer)" in module
    assert 'state.brandingLogoEnabled = enabled' in module
    assert 'state.brandingSloganEnabled = enabled' in module
    assert 'firstTemplateId(layer)' in module
    assert 'role="radio"' in module
    assert "draftTemplateId = selectedTemplateId(activeDrawerLayer)" in module
    assert "confirmBrandMaterialDrawer" in module
    assert "drawerQuery.trim().toLocaleLowerCase()" in module
    assert 'form.append("branding_logo_template_id", state.selectedBrandingLogoTemplateId)' in submit
    assert 'form.append("branding_slogan_template_id", state.selectedBrandingSloganTemplateId)' in submit
    assert 'form.append("branding_template_id", state.selectedBrandingTemplateId)' not in submit
    assert ".brand-material-row" in redesign
    assert ".brand-material-toggle" in redesign
    assert ".brand-material-drawer" in redesign
    assert "height: 100dvh" in redesign


def test_frontend_brand_layer_contracts_cover_draft_dedupe_restore_and_results() -> None:
    module = (ROOT / "codex_image/webui/frontend/src/brand-materials.ts").read_text(encoding="utf-8")
    submit = (ROOT / "codex_image/webui/frontend/src/task-submit.ts").read_text(encoding="utf-8")
    result_actions = (ROOT / "codex_image/webui/frontend/src/brand-result-actions.ts").read_text(encoding="utf-8")
    state_defaults = (ROOT / "codex_image/webui/frontend/src/state-defaults.ts").read_text(encoding="utf-8")
    en = (ROOT / "codex_image/webui/frontend/src/i18n/en.ts").read_text(encoding="utf-8")
    zh = (ROOT / "codex_image/webui/frontend/src/i18n/zh-cn.ts").read_text(encoding="utf-8")

    assert "brandingLogoEnabled: false" in state_defaults
    assert "brandingSloganEnabled: false" in state_defaults
    assert "selectedBrandingLogoTemplateId" in state_defaults
    assert "selectedBrandingSloganTemplateId" in state_defaults
    assert 'document.documentElement.dataset.theme === "dark" ? "light-assets" : "dark-assets"' in module
    assert 'if (layer === "slogan")' in module
    assert "seen.has(key)" in module
    assert "placementSignature(template, \"slogan\")" in module
    assert "sloganMaterialSignature" in module
    assert "canonicalTemplateId" in module
    assert "normalizeBrandLayerSelections" in module
    assert "if (!state.brandTemplatesLoaded) return" in module
    assert "setSelectedTemplateId(layer, canonicalId)" in module
    assert "setBrandLayerEnabled(layer, !layerEnabled(layer))" in module
    assert "draftTemplateId = String(button.dataset.brandDrawerTemplateId || \"\")" in module
    assert "selectBrandLayerTemplate(activeDrawerLayer, draftTemplateId)" in module
    assert "closeBrandMaterialDrawer()" in module
    assert "restoreBrandingSelectionFromTask" in submit
    assert 'task?.params?.branding_request?.layers?.[layer]?.template_id' in submit
    assert submit.index('taskBrandingLayerTemplateId(task, "logo")') < submit.index('taskBrandingField(task, "branding_logo_template_id")')
    assert submit.index('taskBrandingLayerTemplateId(task, "slogan")') < submit.index('taskBrandingField(task, "branding_slogan_template_id")')
    assert 'taskBrandingField(task, "branding_template_id")' in submit
    assert "state.brandingLogoEnabled = Boolean(restoredLogoId)" in submit
    assert "state.brandingSloganEnabled = Boolean(restoredSloganId)" in submit
    assert "brandingLayerSummaryForTask" in result_actions
    assert 'layerTemplateId(resultBranding, "logo")' in result_actions
    assert 'layerTemplateId(resultBranding, "slogan")' in result_actions
    assert result_actions.index('layerTemplateId(resultBranding, "logo")') < result_actions.index('layerTemplateId(brandingRequest, "logo")')
    assert result_actions.index('layerTemplateId(resultBranding, "slogan")') < result_actions.index('layerTemplateId(brandingRequest, "slogan")')
    assert "brand-layer-summary" in result_actions
    assert "summary.textContent = layerSummary" in result_actions
    assert '<span class="brand-layer-summary">${layerSummary}</span>' not in result_actions
    assert 'parts.push(`${templateName(appliedLogoId)} Logo`)' in result_actions
    assert 'parts.push(t("brand.sloganMaterialName"' in result_actions
    assert 'templateName(appliedSloganId)' not in result_actions
    assert '"brand.logoLayer": "Logo"' in en
    assert '"brand.sloganLayer": "Slogan and business signature"' in en
    assert '"brand.sloganMaterialName": "Brand slogan and business signature"' in en
    assert '"brand.logoLayer": "Logo"' in zh
    assert '"brand.sloganLayer": "口号与业务落款"' in zh
    assert '"brand.sloganMaterialName": "品牌口号与业务落款"' in zh
    assert 'layer === "slogan" ? translate("brand.sloganMaterialName")' in module


def test_frontend_brand_runtime_prunes_invalid_restore_and_refocuses_replaced_trigger() -> None:
    node = shutil.which("node")
    if node is None:
        import pytest

        pytest.skip("node is required for frontend behavior checks")
    brand_path = ROOT / "codex_image/webui/frontend/src/brand-materials.ts"
    submit_path = ROOT / "codex_image/webui/frontend/src/task-submit.ts"
    harness = textwrap.dedent(
        """
        const fs = require("fs");
        const ts = require("typescript");
        const vm = require("vm");

        class ClassList {
          constructor() { this.values = new Set(); }
          add(value) { this.values.add(value); }
          remove(value) { this.values.delete(value); }
          contains(value) { return this.values.has(value); }
          toggle(value, force) {
            const enabled = force === undefined ? !this.values.has(value) : Boolean(force);
            if (enabled) this.values.add(value); else this.values.delete(value);
            return enabled;
          }
        }
        class Trigger {
          constructor(name) {
            this.name = name;
            this.attributes = {};
            this.dataset = { brandLayerOpen: "logo" };
            this.isConnected = true;
            this.focusCount = 0;
          }
          setAttribute(name, value) { this.attributes[name] = String(value); }
          focus() { this.focusCount += 1; }
          addEventListener() {}
        }
        class EventButton {
          addEventListener(type, callback) { if (type === "click") this.click = callback; }
        }

        let renderCount = 0;
        let currentTrigger = new Trigger("initial");
        const materialList = {
          addEventListener() {},
          replaceChildren() {},
          querySelector(selector) {
            return selector === '[data-brand-layer-open="logo"]' ? currentTrigger : null;
          },
          set innerHTML(value) {
            this.value = value;
            currentTrigger.isConnected = false;
            currentTrigger = new Trigger(`rendered-${++renderCount}`);
          },
          get innerHTML() { return this.value || ""; },
        };
        const drawer = { classList: new ClassList(), setAttribute() {} };
        const confirmButton = new EventButton();
        const state = {
          brandTemplatesLoaded: true,
          brandTemplates: [
            {
              template_id: "valid-template",
              name: "Valid",
              recipe: {
                asset_variants: {
                  "light-assets": { logo: "logo-light", slogan: "slogan-light" },
                  "dark-assets": { logo: "logo-dark", slogan: "slogan-dark" },
                },
                placements: {
                  square: { logo: { anchor: "top-left", width_ratio: 0.18 }, slogan: { anchor: "bottom-center", width_ratio: 0.35 } },
                  portrait: { logo: { anchor: "top-left", width_ratio: 0.18 }, slogan: { anchor: "bottom-center", width_ratio: 0.35 } },
                  landscape: { logo: { anchor: "top-left", width_ratio: 0.18 }, slogan: { anchor: "bottom-center", width_ratio: 0.35 } },
                },
              },
            },
            {
              template_id: "incomplete-template",
              name: "Incomplete",
              recipe: {
                asset_variants: {
                  "light-assets": { logo: "logo-light" },
                  "dark-assets": {},
                },
                placements: {
                  square: { logo: { anchor: "top-left", width_ratio: 0.18 } },
                },
              },
            },
          ],
          brandingLogoEnabled: false,
          brandingSloganEnabled: false,
          selectedBrandingLogoTemplateId: "",
          selectedBrandingSloganTemplateId: "",
          selectedBrandingTemplateId: "",
        };
        const els = {
          brandMaterialPicker: { classList: new ClassList() },
          brandMaterialList: materialList,
          brandMaterialDrawer: drawer,
          brandMaterialDrawerBackdrop: { classList: new ClassList(), addEventListener() {} },
          brandMaterialDrawerConfirm: confirmButton,
          brandMaterialOpenButton: new Trigger("compat-hidden"),
        };
        const bridge = {
          state,
          els,
          methods: {
            closePromptTemplateDrawer() {},
            closeGallery() {},
            updateRequestPreview() {},
            escapeHtml(value) { return String(value ?? ""); },
          },
        };
        const document = {
          documentElement: { dataset: { theme: "light" } },
          body: { classList: new ClassList() },
          activeElement: null,
          addEventListener() {},
        };
        const window = { __codexImageWebUI: bridge, setTimeout(callback) { callback(); } };
        class MutationObserver { constructor(callback) { this.callback = callback; } observe() {} }

        function load(path) {
          const code = ts.transpileModule(fs.readFileSync(path, "utf8"), {
            compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
          }).outputText;
          const module = { exports: {} };
          vm.runInNewContext(code, {
            module, exports: module.exports, console, window, document,
            MutationObserver, HTMLElement: Trigger, Element: Trigger,
            require(name) {
              if (name === "./state") return { getLegacyBridge: () => bridge };
              if (name === "./i18n") return {
                LOCALE_CHANGE_EVENT: "locale-change",
                translate: (key) => key === "brand.sloganMaterialName" ? "Brand slogan and business signature" : key,
              };
              throw new Error(`unexpected require: ${name}`);
            },
          });
          return module.exports;
        }

        const brandModule = load(__BRAND_PATH__);
        brandModule.initBrandMaterialsFeature();
        if ((materialList.value || "").includes("Incomplete")) {
          throw new Error("incomplete layer template remained selectable");
        }
        const submitModule = load(__SUBMIT_PATH__);
        submitModule.initTaskSubmitFeature();

        bridge.methods.restoreBrandingSelectionFromTask({
          params: { branding_request: { layers: {
            logo: { template_id: "archived-logo" },
            slogan: { template_id: "archived-slogan" },
          } } },
        });
        if (state.brandingLogoEnabled || state.brandingSloganEnabled) {
          throw new Error("invalid restored layers remained enabled after templates loaded");
        }
        if (state.selectedBrandingLogoTemplateId || state.selectedBrandingSloganTemplateId) {
          throw new Error("invalid restored template ids were not pruned");
        }
        const payload = {};
        bridge.methods.appendBrandingPreviewFields(payload);
        if ("branding_logo_template_id" in payload || "branding_slogan_template_id" in payload) {
          throw new Error("pruned restored ids leaked into submit payload");
        }

        state.selectedBrandingLogoTemplateId = "valid-template";
        state.brandingLogoEnabled = true;
        currentTrigger = new Trigger("before-confirm");
        const detachedTrigger = currentTrigger;
        bridge.methods.openBrandMaterialDrawer(detachedTrigger, "logo");
        if (detachedTrigger.attributes["aria-expanded"] !== "true") {
          throw new Error("real layer trigger did not expose the open drawer state");
        }
        confirmButton.click();
        if (currentTrigger === detachedTrigger || detachedTrigger.isConnected) {
          throw new Error("confirm did not replace the layer trigger during render");
        }
        if (detachedTrigger.focusCount !== 0 || currentTrigger.focusCount !== 1) {
          throw new Error("drawer close did not refocus the newly rendered layer trigger");
        }
        if (currentTrigger.attributes["aria-expanded"] !== "false") {
          throw new Error("new layer trigger retained stale expanded state after close");
        }
        """
    ).replace("__BRAND_PATH__", json.dumps(str(brand_path))).replace(
        "__SUBMIT_PATH__", json.dumps(str(submit_path))
    )
    result = subprocess.run([node, "-e", harness], cwd=ROOT, check=False, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_workspace_places_prompt_before_materials_and_output_settings() -> None:
    html = (ROOT / "codex_image/webui/static/index.html").read_text(encoding="utf-8")

    prompt_index = html.index('class="panel prompt-panel"')
    materials_index = html.index('class="panel image-panel"')
    output_index = html.index('class="panel output-panel"')

    assert prompt_index < materials_index < output_index
