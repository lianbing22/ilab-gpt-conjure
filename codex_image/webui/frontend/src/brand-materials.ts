import { LOCALE_CHANGE_EVENT, translate } from "./i18n";
import { getLegacyBridge } from "./state";

const state = getLegacyBridge().state;
const els = getLegacyBridge().els;

let brandMaterialsInitialized = false;

function legacyMethod(name: string, ...args: any[]): any {
  return getLegacyBridge().methods[name]?.(...args);
}

function escapeHtml(value: unknown): string {
  return legacyMethod("escapeHtml", value) || "";
}

function previewAssetId(template: any): string {
  return String(template?.recipe?.asset_variants?.["dark-assets"]?.logo || "");
}

function renderBrandMaterials(): void {
  if (!els.brandMaterialPicker || !els.brandMaterialList) return;
  const templates = Array.isArray(state.brandTemplates) ? state.brandTemplates : [];
  els.brandMaterialPicker.classList.toggle("hidden", templates.length === 0);
  if (!templates.length) {
    els.brandMaterialList.replaceChildren();
    return;
  }

  const options = [
    {
      template_id: "",
      name: translate("brand.materialsNone"),
      preview_id: "",
    },
    ...templates.map((template: any) => ({
      template_id: String(template.template_id || ""),
      name: String(template.name || template.template_id || ""),
      preview_id: previewAssetId(template),
    })),
  ];
  els.brandMaterialList.innerHTML = options.map((option: any) => {
    const selected = option.template_id === state.selectedBrandingTemplateId;
    const preview = option.preview_id
      ? `<img src="/api/brand/assets/${encodeURIComponent(option.preview_id)}/image" alt="" loading="lazy" decoding="async">`
      : `<span class="brand-material-none-mark" aria-hidden="true">—</span>`;
    return `
      <button class="brand-material-option${selected ? " active" : ""}" type="button"
        role="radio" aria-checked="${selected ? "true" : "false"}"
        data-brand-template-id="${escapeHtml(option.template_id)}">
        <span class="brand-material-preview">${preview}</span>
        <span class="brand-material-name">${escapeHtml(option.name)}</span>
      </button>
    `;
  }).join("");
}

function selectBrandTemplate(templateId: unknown): void {
  const cleanId = String(templateId || "");
  const exists = !cleanId || state.brandTemplates.some((template: any) => template.template_id === cleanId);
  state.selectedBrandingTemplateId = exists ? cleanId : "";
  renderBrandMaterials();
  legacyMethod("updateRequestPreview");
}

async function refreshBrandTemplates(): Promise<void> {
  try {
    const response = await fetch("/api/brand/templates");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "brand_templates_load_failed");
    state.brandTemplates = Array.isArray(data.templates) ? data.templates : [];
    if (
      state.selectedBrandingTemplateId
      && !state.brandTemplates.some((template: any) => template.template_id === state.selectedBrandingTemplateId)
    ) {
      state.selectedBrandingTemplateId = "";
    }
  } catch {
    state.brandTemplates = [];
    state.selectedBrandingTemplateId = "";
  }
  renderBrandMaterials();
}

function handleBrandMaterialClick(event: Event): void {
  const target = event.target instanceof Element ? event.target : null;
  const button = target?.closest("[data-brand-template-id]") as HTMLElement | null;
  if (!button) return;
  selectBrandTemplate(button.dataset.brandTemplateId || "");
}

export function initBrandMaterialsFeature(): void {
  if (brandMaterialsInitialized) return;
  brandMaterialsInitialized = true;
  els.brandMaterialList?.addEventListener("click", handleBrandMaterialClick);
  document.addEventListener(LOCALE_CHANGE_EVENT, renderBrandMaterials);
  Object.assign(getLegacyBridge().methods, {
    refreshBrandTemplates,
    renderBrandMaterials,
    selectBrandTemplate,
  });
}
