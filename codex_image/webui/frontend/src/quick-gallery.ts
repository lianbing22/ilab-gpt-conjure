import { getLegacyBridge } from "./state";
import { formatTranslation } from "./i18n";
import { prefersReducedMotion } from "./webui-utils";

const bridge = getLegacyBridge();
const state = bridge.state;
const els = bridge.els;

let quickGalleryFeatureInitialized = false;

function legacyMethod(name: string, ...args: any[]): any {
  const method = getLegacyBridge().methods[name];
  if (typeof method !== "function") {
    throw new Error("Legacy method " + name + " is not initialized");
  }
  return method(...args);
}

function escapeHtml(value: any): string { return legacyMethod("escapeHtml", value); }
function addGalleryInput(item: any, options?: any): void { legacyMethod("addGalleryInput", item, options); }
function filterGalleryItems(category?: any): any[] { return legacyMethod("filterGalleryItems", category); }
function findGalleryItem(itemId: any): any { return legacyMethod("findGalleryItem", itemId); }
function categoryLabel(category: any): string { return legacyMethod("categoryLabel", category); }
function renderGalleryCategoryControls(): void { legacyMethod("renderGalleryCategoryControls"); }

function renderQuickGalleryDock() {
  renderGalleryCategoryControls();
  renderQuickGalleryList();
}

function selectedGalleryItemIds(): Set<string> {
  const ids = new Set<string>();
  state.images.forEach((source: any) => {
    if (source?.kind === "gallery" && source?.id) ids.add(String(source.id));
  });
  return ids;
}

function renderQuickGalleryList() {
  if (!els.quickGalleryList) return;
  const query = String(state.quickGallerySearchQuery || "").trim().toLowerCase();
  const selectedIds = selectedGalleryItemIds();
  const items = filterGalleryItems().filter((item: any) => {
    if (!query) return true;
    const nameKey = String(item.name_key || item.name || "").toLowerCase();
    const name = String(item.name || "").toLowerCase();
    return name.includes(query) || nameKey.includes(query);
  });
  if (!items.length) {
    els.quickGalleryList.innerHTML = `<div class="quick-gallery-empty">${escapeHtml(
      formatTranslation(
        query ? "quickGallery.noResults" : "quickGallery.empty",
        { category: categoryLabel(state.activeGalleryCategory) }
      )
    )}</div>`;
    return;
  }
  els.quickGalleryList.innerHTML = items.map((item: any) => {
    const selected = selectedIds.has(String(item.id));
    return `
    <button class="quick-gallery-thumb${selected ? " selected" : ""}" type="button"
      data-quick-gallery-use="${escapeHtml(item.id)}"
      title="${escapeHtml(item.name)}">
      <img src="/api/gallery/${encodeURIComponent(String(item.id))}/thumbnail" alt="" loading="lazy" decoding="async">
      <span class="quick-gallery-thumb-name">${escapeHtml(item.name)}</span>
      <span class="quick-gallery-thumb-check" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false"><path d="M4.5 12.5 10 18 19.5 6.5" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </span>
    </button>`;
  }).join("");
  els.quickGalleryList.scrollTop = 0;
}

function updateQuickGallerySelection() {
  if (!els.quickGalleryList) return;
  const selectedIds = selectedGalleryItemIds();
  els.quickGalleryList.querySelectorAll("[data-quick-gallery-use]").forEach((button: any) => {
    button.classList.toggle("selected", selectedIds.has(String(button.dataset.quickGalleryUse)));
  });
}

function animateGalleryItemToInput(item: any, fromEl: any) {
  if (prefersReducedMotion()) return;
  if (!item?.image_url || !fromEl || !els.imageStrip) return;
  const sourceRect = fromEl.getBoundingClientRect();
  const targetRect = (els.imageStrip.querySelector(".thumb:last-child") || els.imageUploadSource || els.imageStrip).getBoundingClientRect();
  if (!sourceRect || !targetRect) return;
  const clone = document.createElement("img");
  clone.className = "gallery-fly-clone";
  clone.src = item.image_url;
  clone.alt = "";
  clone.style.left = `${sourceRect.left}px`;
  clone.style.top = `${sourceRect.top}px`;
  clone.style.width = `${sourceRect.width}px`;
  clone.style.height = `${sourceRect.height}px`;
  document.body.appendChild(clone);
  const deltaX = targetRect.left + (targetRect.width / 2) - sourceRect.left - (sourceRect.width / 2);
  const deltaY = targetRect.top + (targetRect.height / 2) - sourceRect.top - (sourceRect.height / 2);
  clone.animate([
    { transform: "translate3d(0, 0, 0) scale(1)", opacity: 0.96 },
    { transform: `translate3d(${deltaX}px, ${deltaY}px, 0) scale(0.28)`, opacity: 0.18 },
  ], { duration: 220, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" }).addEventListener("finish", () => clone.remove());
}

export function initQuickGalleryFeature() {
  if (quickGalleryFeatureInitialized) return;
  quickGalleryFeatureInitialized = true;
  Object.assign(getLegacyBridge().methods, {
    renderQuickGalleryDock,
    renderQuickGalleryList,
    updateQuickGallerySelection,
    animateGalleryItemToInput,
  });

  els.quickGallerySearch?.addEventListener("input", () => {
    state.quickGallerySearchQuery = els.quickGallerySearch?.value || "";
    renderQuickGalleryList();
  });

  els.quickGalleryList?.addEventListener("click", (event: any) => {
    const button = event.target.closest?.("[data-quick-gallery-use]");
    if (!button || !els.quickGalleryList?.contains(button)) return;
    const item = findGalleryItem(button.dataset.quickGalleryUse);
    if (!item) return;
    const sourceIndex = state.images.findIndex((source: any) => source.kind === "gallery" && source.id === item.id);
    if (sourceIndex >= 0) {
      const removedSource = state.images[sourceIndex];
      legacyMethod("revokeUploadPreviewUrl", removedSource, { ignoredCurrentSources: new Set([removedSource]) });
      state.images.splice(sourceIndex, 1);
      legacyMethod("syncPromptGalleryMentionsFromInputs");
      if (!state.images.length) legacyMethod("setMode", "generate");
      legacyMethod("renderImageStrip");
      legacyMethod("updateRequestPreview");
      button.classList.remove("selected");
      return;
    }
    addGalleryInput(item);
    button.classList.add("selected");
    animateGalleryItemToInput(item, button);
  });

  const openModal = () => {
    renderQuickGalleryDock();
    els.quickGalleryModal.classList.remove("hidden");
    els.quickGalleryModal.setAttribute("aria-hidden", "false");
    els.quickGalleryOpenButton?.setAttribute("aria-expanded", "true");
    requestAnimationFrame(() => els.quickGallerySearch?.focus({ preventScroll: true }));
  };

  const closeModal = () => {
    els.quickGalleryModal.classList.add("hidden");
    els.quickGalleryModal.setAttribute("aria-hidden", "true");
    els.quickGalleryOpenButton?.setAttribute("aria-expanded", "false");
  };

  els.quickGalleryOpenButton?.addEventListener("click", openModal);
  els.quickGalleryModalClose?.addEventListener("click", () => { closeModal(); });
  els.quickGalleryDoneButton?.addEventListener("click", () => { closeModal(); });
  els.quickGalleryModal?.addEventListener("click", (event: any) => {
    if (event.target === els.quickGalleryModal) closeModal();
  });
}