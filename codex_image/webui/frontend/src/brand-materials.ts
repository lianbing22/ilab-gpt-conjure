import { LOCALE_CHANGE_EVENT, translate } from "./i18n";
import { getLegacyBridge } from "./state";

const state = getLegacyBridge().state;
const els = getLegacyBridge().els;

let brandMaterialsInitialized = false;
let draftTemplateId = "";
let drawerQuery = "";
let lastDrawerTrigger: HTMLElement | null = null;

function legacyMethod(name: string, ...args: any[]): any {
  return getLegacyBridge().methods[name]?.(...args);
}

function escapeHtml(value: unknown): string {
  return legacyMethod("escapeHtml", value) || "";
}

function previewAssetId(template: any): string {
  return String(template?.recipe?.asset_variants?.["dark-assets"]?.logo || "");
}

function templateOptions(): any[] {
  const templates = Array.isArray(state.brandTemplates) ? state.brandTemplates : [];
  return [
    { template_id: "", name: translate("brand.materialsNone"), preview_id: "" },
    ...templates.map((template: any) => ({
      template_id: String(template.template_id || ""),
      name: String(template.name || template.template_id || ""),
      preview_id: previewAssetId(template),
    })),
  ];
}

function previewHtml(option: any, large = false): string {
  if (!option.preview_id) {
    return `<span class="brand-material-none-mark" aria-hidden="true">—</span>`;
  }
  const sizeClass = large ? " brand-material-drawer-preview" : "";
  return `<span class="brand-material-preview${sizeClass}"><img src="/api/brand/assets/${encodeURIComponent(option.preview_id)}/image" alt="" loading="lazy" decoding="async"></span>`;
}

function optionHtml(option: any, selected: boolean): string {
  return `
    <button class="brand-material-option${selected ? " active" : ""}" type="button"
      role="radio" aria-checked="${selected ? "true" : "false"}"
      data-brand-template-id="${escapeHtml(option.template_id)}">
      ${previewHtml(option)}
      <span class="brand-material-name">${escapeHtml(option.name)}</span>
      <span class="brand-material-check" aria-hidden="true">✓</span>
    </button>
  `;
}

function quickOptions(options: any[]): any[] {
  const visible = options.slice(0, 4);
  const selected = options.find((option) => option.template_id === state.selectedBrandingTemplateId);
  if (selected && !visible.includes(selected)) visible[visible.length - 1] = selected;
  return visible;
}

function renderBrandMaterials(): void {
  if (!els.brandMaterialPicker || !els.brandMaterialList) return;
  const templates = Array.isArray(state.brandTemplates) ? state.brandTemplates : [];
  els.brandMaterialPicker.classList.toggle("hidden", templates.length === 0);
  if (!templates.length) {
    els.brandMaterialList.replaceChildren();
    renderBrandMaterialDrawer();
    return;
  }

  const options = quickOptions(templateOptions());
  els.brandMaterialList.innerHTML = options
    .map((option: any) => optionHtml(option, option.template_id === state.selectedBrandingTemplateId))
    .join("");
  renderBrandMaterialDrawer();
}

function filteredDrawerOptions(): any[] {
  const query = drawerQuery.trim().toLocaleLowerCase();
  if (!query) return templateOptions();
  return templateOptions().filter((option) => String(option.name || "").toLocaleLowerCase().includes(query));
}

function drawerOptionHtml(option: any): string {
  const selected = option.template_id === draftTemplateId;
  return `
    <button class="brand-material-drawer-option${selected ? " active" : ""}" type="button"
      role="radio" aria-checked="${selected ? "true" : "false"}"
      data-brand-drawer-template-id="${escapeHtml(option.template_id)}">
      <span class="brand-material-drawer-visual">${previewHtml(option, true)}</span>
      <span class="brand-material-drawer-copy">
        <strong>${escapeHtml(option.name)}</strong>
        <span>${selected ? escapeHtml(translate("brand.selected")) : escapeHtml(translate("brand.clickToSelect"))}</span>
      </span>
      <span class="brand-material-drawer-check" aria-hidden="true">✓</span>
    </button>
  `;
}

function renderBrandMaterialDrawer(): void {
  if (!els.brandMaterialDrawerList) return;
  const options = filteredDrawerOptions();
  els.brandMaterialDrawerList.innerHTML = options.map(drawerOptionHtml).join("");
  els.brandMaterialDrawerEmpty?.classList.toggle("hidden", options.length > 0);
  if (els.brandMaterialDrawerConfirm) {
    const selected = templateOptions().find((option) => option.template_id === draftTemplateId);
    els.brandMaterialDrawerConfirm.textContent = selected?.template_id
      ? `${translate("brand.confirmUse")} ${selected.name}`
      : translate("brand.confirmNone");
  }
}

function selectBrandTemplate(templateId: unknown): void {
  const cleanId = String(templateId || "");
  const exists = !cleanId || state.brandTemplates.some((template: any) => template.template_id === cleanId);
  state.selectedBrandingTemplateId = exists ? cleanId : "";
  draftTemplateId = state.selectedBrandingTemplateId;
  renderBrandMaterials();
  legacyMethod("updateRequestPreview");
}

function openBrandMaterialDrawer(trigger?: HTMLElement | null): void {
  legacyMethod("closePromptTemplateDrawer", { restoreFocus: false });
  legacyMethod("closeGallery", { restoreFocus: false });
  draftTemplateId = String(state.selectedBrandingTemplateId || "");
  drawerQuery = "";
  lastDrawerTrigger = trigger || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
  if (els.brandMaterialSearch) els.brandMaterialSearch.value = "";
  renderBrandMaterialDrawer();
  els.brandMaterialDrawer?.classList.add("open");
  els.brandMaterialDrawer?.setAttribute("aria-hidden", "false");
  els.brandMaterialDrawerBackdrop?.classList.remove("hidden");
  els.brandMaterialOpenButton?.setAttribute("aria-expanded", "true");
  document.body.classList.add("brand-material-drawer-open");
  window.setTimeout(() => els.brandMaterialSearch?.focus?.({ preventScroll: true }), 0);
}

function closeBrandMaterialDrawer(options: { restoreFocus?: boolean } = {}): void {
  const restoreFocus = options.restoreFocus !== false;
  els.brandMaterialDrawer?.classList.remove("open");
  els.brandMaterialDrawer?.setAttribute("aria-hidden", "true");
  els.brandMaterialDrawerBackdrop?.classList.add("hidden");
  els.brandMaterialOpenButton?.setAttribute("aria-expanded", "false");
  document.body.classList.remove("brand-material-drawer-open");
  draftTemplateId = String(state.selectedBrandingTemplateId || "");
  if (restoreFocus) {
    (lastDrawerTrigger || els.brandMaterialOpenButton)?.focus?.({ preventScroll: true });
  }
}

function confirmBrandMaterialDrawer(): void {
  selectBrandTemplate(draftTemplateId);
  closeBrandMaterialDrawer();
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
  draftTemplateId = String(state.selectedBrandingTemplateId || "");
  renderBrandMaterials();
}

function handleBrandMaterialClick(event: Event): void {
  const target = event.target instanceof Element ? event.target : null;
  const button = target?.closest("[data-brand-template-id]") as HTMLElement | null;
  if (!button) return;
  selectBrandTemplate(button.dataset.brandTemplateId || "");
}

function handleDrawerMaterialClick(event: Event): void {
  const target = event.target instanceof Element ? event.target : null;
  const button = target?.closest("[data-brand-drawer-template-id]") as HTMLElement | null;
  if (!button) return;
  draftTemplateId = String(button.dataset.brandDrawerTemplateId || "");
  renderBrandMaterialDrawer();
}

function handleDrawerSearch(event: Event): void {
  drawerQuery = event.target instanceof HTMLInputElement ? event.target.value : "";
  renderBrandMaterialDrawer();
}

function handleDrawerKeydown(event: KeyboardEvent): void {
  const drawer = els.brandMaterialDrawer as HTMLElement | null;
  if (!drawer?.classList.contains("open")) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeBrandMaterialDrawer();
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = Array.from(
    drawer.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), [tabindex]:not([tabindex='-1'])"),
  ).filter((node) => !node.hidden && node.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}

export function initBrandMaterialsFeature(): void {
  if (brandMaterialsInitialized) return;
  brandMaterialsInitialized = true;
  els.brandMaterialList?.addEventListener("click", handleBrandMaterialClick);
  els.brandMaterialOpenButton?.addEventListener("click", (event: Event) => openBrandMaterialDrawer(event.currentTarget as HTMLElement));
  els.brandMaterialDrawerList?.addEventListener("click", handleDrawerMaterialClick);
  els.brandMaterialDrawerClose?.addEventListener("click", () => closeBrandMaterialDrawer());
  els.brandMaterialDrawerCancel?.addEventListener("click", () => closeBrandMaterialDrawer());
  els.brandMaterialDrawerConfirm?.addEventListener("click", confirmBrandMaterialDrawer);
  els.brandMaterialDrawerBackdrop?.addEventListener("click", () => closeBrandMaterialDrawer());
  els.brandMaterialSearch?.addEventListener("input", handleDrawerSearch);
  document.addEventListener("keydown", handleDrawerKeydown);
  document.addEventListener(LOCALE_CHANGE_EVENT, renderBrandMaterials);
  Object.assign(getLegacyBridge().methods, {
    refreshBrandTemplates,
    renderBrandMaterials,
    selectBrandTemplate,
    openBrandMaterialDrawer,
    closeBrandMaterialDrawer,
  });
}
