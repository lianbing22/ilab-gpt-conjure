import { LOCALE_CHANGE_EVENT, translate } from "./i18n";
import { getLegacyBridge } from "./state";

const state = getLegacyBridge().state;
const els = getLegacyBridge().els;

type BrandLayer = "logo" | "slogan";
type ToneKey = "light-assets" | "dark-assets";

interface BrandMaterialOption {
  template_id: string;
  name: string;
  preview_id: string;
  layer: BrandLayer;
}

const BRAND_LAYERS: BrandLayer[] = ["logo", "slogan"];
const BRAND_LAYOUTS = ["square", "portrait", "landscape"] as const;
const BRAND_TONES: ToneKey[] = ["light-assets", "dark-assets"];

let brandMaterialsInitialized = false;
let activeDrawerLayer: BrandLayer = "logo";
let draftTemplateId = "";
let drawerQuery = "";
let lastDrawerTrigger: HTMLElement | null = null;
let themeObserver: MutationObserver | null = null;

function legacyMethod(name: string, ...args: any[]): any {
  return getLegacyBridge().methods[name]?.(...args);
}

function escapeHtml(value: unknown): string {
  return legacyMethod("escapeHtml", value) || "";
}

function templates(): any[] {
  return Array.isArray(state.brandTemplates) ? state.brandTemplates : [];
}

function layerEnabled(layer: BrandLayer): boolean {
  return layer === "logo" ? Boolean(state.brandingLogoEnabled) : Boolean(state.brandingSloganEnabled);
}

function setLayerEnabled(layer: BrandLayer, enabled: boolean): void {
  if (layer === "logo") {
    state.brandingLogoEnabled = enabled;
  } else {
    state.brandingSloganEnabled = enabled;
  }
}

function selectedTemplateId(layer: BrandLayer): string {
  return layer === "logo"
    ? String(state.selectedBrandingLogoTemplateId || "")
    : String(state.selectedBrandingSloganTemplateId || "");
}

function setSelectedTemplateId(layer: BrandLayer, templateId: string): void {
  if (layer === "logo") {
    state.selectedBrandingLogoTemplateId = templateId;
  } else {
    state.selectedBrandingSloganTemplateId = templateId;
  }
  state.selectedBrandingTemplateId = state.selectedBrandingLogoTemplateId || state.selectedBrandingSloganTemplateId || "";
}

function effectivePreviewTone(): ToneKey {
  return document.documentElement.dataset.theme === "dark" ? "light-assets" : "dark-assets";
}

function previewAssetId(template: any, layer: BrandLayer): string {
  const variants = template?.recipe?.asset_variants || {};
  return String(variants?.[effectivePreviewTone()]?.[layer] || variants?.["dark-assets"]?.[layer] || variants?.["light-assets"]?.[layer] || "");
}

function placementSignature(template: any, layer: BrandLayer): string {
  const placements = template?.recipe?.placements || {};
  const layerPlacements: Record<string, unknown> = {};
  Object.keys(placements).sort().forEach((layout) => {
    const cfg = placements?.[layout]?.[layer];
    if (cfg) layerPlacements[layout] = cfg;
  });
  return JSON.stringify(layerPlacements);
}

function templateSupportsLayer(template: any, layer: BrandLayer): boolean {
  const recipe = template?.recipe || {};
  const variants = recipe.asset_variants || {};
  const placements = recipe.placements || {};
  const hasAssets = BRAND_TONES.every((tone) => String(variants?.[tone]?.[layer] || "").trim());
  const hasPlacements = BRAND_LAYOUTS.every((layout) => {
    const placement = placements?.[layout]?.[layer];
    return placement && Number(placement.width_ratio || 0) > 0;
  });
  return hasAssets && hasPlacements;
}

function sloganMaterialSignature(template: any): string {
  const variants = template?.recipe?.asset_variants || {};
  return [
    String(variants?.["light-assets"]?.slogan || ""),
    String(variants?.["dark-assets"]?.slogan || ""),
    placementSignature(template, "slogan"),
  ].join("|");
}

function layerOptions(layer: BrandLayer): BrandMaterialOption[] {
  const seen = new Set<string>();
  const options: BrandMaterialOption[] = [];
  for (const template of templates()) {
    const templateId = String(template.template_id || "");
    if (!templateId || !templateSupportsLayer(template, layer)) continue;
    const previewId = previewAssetId(template, layer);
    if (layer === "slogan") {
      const key = sloganMaterialSignature(template);
      if (seen.has(key)) continue;
      seen.add(key);
    }
    options.push({
      template_id: templateId,
      name: layer === "slogan" ? translate("brand.sloganMaterialName") : String(template.name || templateId),
      preview_id: previewId,
      layer,
    });
  }
  return options;
}

function firstTemplateId(layer: BrandLayer): string {
  return layerOptions(layer)[0]?.template_id || "";
}

function canonicalTemplateId(layer: BrandLayer, templateId: string): string {
  const options = layerOptions(layer);
  if (options.some((option) => option.template_id === templateId)) return templateId;
  if (layer !== "slogan" || !templateId) return "";
  const source = templates().find((template) => String(template?.template_id || "") === templateId);
  if (!source) return "";
  const signature = sloganMaterialSignature(source);
  const canonical = options.find((option) => {
    const template = templates().find((item) => String(item?.template_id || "") === option.template_id);
    return template && sloganMaterialSignature(template) === signature;
  });
  return canonical?.template_id || "";
}

function findOption(layer: BrandLayer, templateId: string): BrandMaterialOption | null {
  const canonicalId = canonicalTemplateId(layer, templateId);
  return layerOptions(layer).find((option) => option.template_id === canonicalId) || null;
}

function layerLabel(layer: BrandLayer): string {
  return translate(layer === "logo" ? "brand.logoLayer" : "brand.sloganLayer");
}

function layerHint(layer: BrandLayer): string {
  return translate(layer === "logo" ? "brand.logoHint" : "brand.sloganHint");
}

function previewHtml(option: BrandMaterialOption | null, large = false): string {
  if (!option?.preview_id) {
    return `<span class="brand-material-none-mark" aria-hidden="true">-</span>`;
  }
  const sizeClass = large ? " brand-material-drawer-preview" : "";
  return `<span class="brand-material-preview${sizeClass}"><img src="/api/brand/assets/${encodeURIComponent(option.preview_id)}/image" alt="" loading="lazy" decoding="async"></span>`;
}

function layerRowHtml(layer: BrandLayer): string {
  const enabled = layerEnabled(layer);
  const selected = findOption(layer, selectedTemplateId(layer));
  const currentName = selected?.name || translate("brand.notSelected");
  const statusKey = enabled ? "brand.enabled" : "brand.disabled";
  const drawerExpanded = activeDrawerLayer === layer && Boolean(els.brandMaterialDrawer?.classList.contains("open"));
  return `
    <div class="brand-material-row" role="listitem" data-brand-layer="${layer}">
      <button class="brand-material-toggle" type="button" role="switch"
        aria-checked="${enabled ? "true" : "false"}"
        aria-label="${escapeHtml(layerLabel(layer))}"
        data-brand-layer-toggle="${layer}">
        <span class="brand-material-switch-knob" aria-hidden="true"></span>
      </button>
      <button class="brand-material-select-row" type="button"
        data-brand-layer-open="${layer}"
        aria-controls="brandMaterialDrawer"
        aria-expanded="${drawerExpanded ? "true" : "false"}"
        aria-label="${escapeHtml(`${layerLabel(layer)} ${currentName}`)}">
        ${previewHtml(selected)}
        <span class="brand-material-row-copy">
          <strong>${escapeHtml(layerLabel(layer))}</strong>
          <span>${escapeHtml(currentName)}</span>
        </span>
        <span class="brand-material-row-state">${escapeHtml(translate(statusKey))}</span>
        <span class="brand-material-arrow" aria-hidden="true">></span>
      </button>
    </div>
  `;
}

export function normalizeBrandLayerSelections(): void {
  if (!state.brandTemplatesLoaded) return;
  for (const layer of BRAND_LAYERS) {
    const selected = selectedTemplateId(layer);
    const canonicalId = canonicalTemplateId(layer, selected);
    if (canonicalId) {
      setSelectedTemplateId(layer, canonicalId);
    } else if (selected) {
      setSelectedTemplateId(layer, "");
      setLayerEnabled(layer, false);
    }
  }
}

function renderBrandMaterials(): void {
  if (!els.brandMaterialPicker || !els.brandMaterialList) return;
  const hasTemplates = templates().length > 0;
  els.brandMaterialPicker.classList.toggle("hidden", !hasTemplates);
  if (!hasTemplates) {
    els.brandMaterialList.replaceChildren();
    renderBrandMaterialDrawer();
    return;
  }
  normalizeBrandLayerSelections();
  els.brandMaterialList.innerHTML = BRAND_LAYERS.map(layerRowHtml).join("");
  renderBrandMaterialDrawer();
}

function filteredDrawerOptions(): BrandMaterialOption[] {
  const query = drawerQuery.trim().toLocaleLowerCase();
  const options = layerOptions(activeDrawerLayer);
  if (!query) return options;
  return options.filter((option) => String(option.name || "").toLocaleLowerCase().includes(query));
}

function drawerOptionHtml(option: BrandMaterialOption): string {
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
  if (els.brandMaterialDrawerTitle) {
    els.brandMaterialDrawerTitle.textContent = layerLabel(activeDrawerLayer);
  }
  if (els.brandMaterialDrawerSummary) {
    els.brandMaterialDrawerSummary.textContent = layerHint(activeDrawerLayer);
  }
  if (els.brandMaterialFilterLabel) {
    els.brandMaterialFilterLabel.textContent = layerLabel(activeDrawerLayer);
  }
  if (els.brandMaterialDrawerConfirm) {
    const selected = findOption(activeDrawerLayer, draftTemplateId);
    els.brandMaterialDrawerConfirm.textContent = selected?.template_id
      ? `${translate("brand.confirmUse")} ${selected.name}`
      : translate("brand.confirmNone");
  }
}

function ensureLayerSelection(layer: BrandLayer): void {
  const selected = selectedTemplateId(layer);
  setSelectedTemplateId(layer, canonicalTemplateId(layer, selected) || firstTemplateId(layer));
}

function selectBrandLayerTemplate(layer: BrandLayer, templateId: unknown): void {
  const cleanId = String(templateId || "");
  setSelectedTemplateId(layer, canonicalTemplateId(layer, cleanId));
  renderBrandMaterials();
  legacyMethod("updateRequestPreview");
}

function setBrandLayerEnabled(layer: BrandLayer, enabled: boolean): void {
  setLayerEnabled(layer, enabled);
  if (enabled) ensureLayerSelection(layer);
  renderBrandMaterials();
  legacyMethod("updateRequestPreview");
}

function layerOpenButton(layer: BrandLayer): HTMLElement | null {
  return els.brandMaterialList?.querySelector?.(`[data-brand-layer-open="${layer}"]`) as HTMLElement | null;
}

function setLayerOpenButtonExpanded(layer: BrandLayer, expanded: boolean): void {
  layerOpenButton(layer)?.setAttribute("aria-expanded", String(expanded));
}

function openBrandMaterialDrawer(trigger?: HTMLElement | null, layer: BrandLayer = "logo"): void {
  legacyMethod("closePromptTemplateDrawer", { restoreFocus: false });
  legacyMethod("closeGallery", { restoreFocus: false });
  setLayerOpenButtonExpanded(activeDrawerLayer, false);
  activeDrawerLayer = layer;
  draftTemplateId = selectedTemplateId(layer) || firstTemplateId(layer);
  drawerQuery = "";
  lastDrawerTrigger = trigger || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
  if (els.brandMaterialSearch) els.brandMaterialSearch.value = "";
  renderBrandMaterialDrawer();
  els.brandMaterialDrawer?.classList.add("open");
  els.brandMaterialDrawer?.setAttribute("aria-hidden", "false");
  els.brandMaterialDrawerBackdrop?.classList.remove("hidden");
  setLayerOpenButtonExpanded(activeDrawerLayer, true);
  document.body.classList.add("brand-material-drawer-open");
  window.setTimeout(() => els.brandMaterialSearch?.focus?.({ preventScroll: true }), 0);
}

function closeBrandMaterialDrawer(options: { restoreFocus?: boolean } = {}): void {
  const restoreFocus = options.restoreFocus !== false;
  els.brandMaterialDrawer?.classList.remove("open");
  els.brandMaterialDrawer?.setAttribute("aria-hidden", "true");
  els.brandMaterialDrawerBackdrop?.classList.add("hidden");
  setLayerOpenButtonExpanded(activeDrawerLayer, false);
  document.body.classList.remove("brand-material-drawer-open");
  draftTemplateId = selectedTemplateId(activeDrawerLayer);
  if (restoreFocus) {
    const currentTrigger = layerOpenButton(activeDrawerLayer);
    (currentTrigger || (lastDrawerTrigger?.isConnected ? lastDrawerTrigger : null) || els.brandMaterialOpenButton)
      ?.focus?.({ preventScroll: true });
  }
}

function confirmBrandMaterialDrawer(): void {
  selectBrandLayerTemplate(activeDrawerLayer, draftTemplateId);
  closeBrandMaterialDrawer();
}

async function refreshBrandTemplates(): Promise<void> {
  try {
    const response = await fetch("/api/brand/templates");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "brand_templates_load_failed");
    state.brandTemplates = Array.isArray(data.templates) ? data.templates : [];
  } catch {
    state.brandTemplates = [];
  }
  state.brandTemplatesLoaded = true;
  normalizeBrandLayerSelections();
  draftTemplateId = selectedTemplateId(activeDrawerLayer);
  renderBrandMaterials();
}

function handleBrandMaterialClick(event: Event): void {
  const target = event.target instanceof Element ? event.target : null;
  const toggle = target?.closest("[data-brand-layer-toggle]") as HTMLElement | null;
  if (toggle) {
    const layer = toggle.dataset.brandLayerToggle as BrandLayer;
    setBrandLayerEnabled(layer, !layerEnabled(layer));
    return;
  }
  const opener = target?.closest("[data-brand-layer-open]") as HTMLElement | null;
  if (!opener) return;
  const layer = opener.dataset.brandLayerOpen as BrandLayer;
  openBrandMaterialDrawer(opener, layer);
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
  els.brandMaterialOpenButton?.addEventListener("click", (event: Event) => openBrandMaterialDrawer(event.currentTarget as HTMLElement, "logo"));
  els.brandMaterialDrawerList?.addEventListener("click", handleDrawerMaterialClick);
  els.brandMaterialDrawerClose?.addEventListener("click", () => closeBrandMaterialDrawer());
  els.brandMaterialDrawerCancel?.addEventListener("click", () => closeBrandMaterialDrawer());
  els.brandMaterialDrawerConfirm?.addEventListener("click", confirmBrandMaterialDrawer);
  els.brandMaterialDrawerBackdrop?.addEventListener("click", () => closeBrandMaterialDrawer());
  els.brandMaterialSearch?.addEventListener("input", handleDrawerSearch);
  document.addEventListener("keydown", handleDrawerKeydown);
  document.addEventListener(LOCALE_CHANGE_EVENT, renderBrandMaterials);
  themeObserver = new MutationObserver(renderBrandMaterials);
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  Object.assign(getLegacyBridge().methods, {
    refreshBrandTemplates,
    renderBrandMaterials,
    normalizeBrandLayerSelections,
    selectBrandTemplate: (templateId: unknown) => {
      for (const layer of BRAND_LAYERS) {
        setSelectedTemplateId(layer, String(templateId || ""));
        setLayerEnabled(layer, Boolean(templateId));
      }
      renderBrandMaterials();
      legacyMethod("updateRequestPreview");
    },
    selectBrandLayerTemplate,
    setBrandLayerEnabled,
    openBrandMaterialDrawer,
    closeBrandMaterialDrawer,
    confirmBrandMaterialDrawer,
  });
}
