/**
 * Brand overlay result actions (ui.md-aligned, step 3-J minimal).
 *
 * Decorates each preview output card with a branded/raw toggle and a branded
 * download link when the task has completed brand compositing for that output.
 * Intentionally decoupled from task-preview.ts: it observes the preview grid
 * and augments cards via the existing data-preview-output-url / dataset hooks,
 * so the 935-line preview module is left untouched.
 *
 * Behaviour:
 *  - If an output has outputs[].branding.status === "completed", show a small
 *    toggle (品牌版 / 原始底图). Default to the branded view.
 *  - The main preview image + the existing download link point at whichever
 *    variant is selected.
 *  - A separate "下载品牌版" link hits /api/tasks/{id}/outputs/{index}/branding/download.
 *  - branding_status pending/running shows a "品牌处理中" badge; failed shows
 *    "重新合成".
 */

import { getLegacyBridge } from "./state";
import { translate } from "./i18n";

const bridge = getLegacyBridge();
const state = bridge.state;
const els = bridge.els;

let observer: MutationObserver | null = null;
let bound = false;

function t(key: string, fallback: string): string {
  const value = translate(key);
  return value && value !== key ? value : fallback;
}

/** Read outputs[].branding for the card's output index from the preview task. */
function brandingForCard(card: HTMLElement): { index: number; branding: any; task: any } | null {
  const taskId = card.dataset.previewTaskId || state.previewTask?.task_id || "";
  const outputUrl = String(card.dataset.previewOutputUrl || "");
  if (!taskId || !outputUrl) return null;
  const task = (state.tasks || []).find((item: any) => String(item.task_id) === String(taskId)) || state.previewTask;
  if (!task || !Array.isArray(task.outputs)) return null;
  // Match the output by its url/file; fall back to the card's slot index.
  const byUrl = task.outputs.find((o: any) => o && (o.url === outputUrl || `/outputs/${o.file}` === outputUrl));
  const output = byUrl || task.outputs.find((o: any, i: number) => previewSlotIndex(card) === i);
  if (!output || !output.branding) return null;
  return { index: Number(output.index) || previewSlotIndex(card) + 1, branding: output.branding, task };
}

function previewSlotIndex(card: HTMLElement): number {
  const siblings = Array.from(els.previewGrid?.querySelectorAll(".preview-card[data-preview-card-key]") || []);
  return Math.max(0, siblings.indexOf(card));
}

function brandingBadgeForTask(task: any): string {
  const status = String(task?.branding_status || "");
  if (status === "running" || status === "pending") {
    return `<span class="brand-badge brand-badge-pending">${t("brand.processing", "品牌处理中")}</span>`;
  }
  if (status === "failed" || status === "partial_failed") {
    return `<span class="brand-badge brand-badge-failed">${t("brand.failed", "品牌合成失败")}</span>`;
  }
  return "";
}

function templateName(templateId: string): string {
  const template = (state.brandTemplates || []).find((item: any) => String(item?.template_id || "") === templateId);
  return String(template?.name || templateId);
}

function layerTemplateId(source: any, layer: "logo" | "slogan"): string {
  return String(source?.layers?.[layer]?.template_id || "");
}

function brandingLayerSummaryForTask(task: any, resultBranding?: any): string {
  const request = task?.request || {};
  const params = task?.params || {};
  const brandingRequest = params.branding_request || {};
  const logoId = layerTemplateId(resultBranding, "logo")
    || layerTemplateId(brandingRequest, "logo")
    || String(request.branding_logo_template_id || brandingRequest.branding_logo_template_id || brandingRequest.logo_template_id || "");
  const sloganId = layerTemplateId(resultBranding, "slogan")
    || layerTemplateId(brandingRequest, "slogan")
    || String(request.branding_slogan_template_id || brandingRequest.branding_slogan_template_id || brandingRequest.slogan_template_id || "");
  const legacyId = String(request.branding_template_id || brandingRequest.branding_template_id || brandingRequest.template_id || "");
  const appliedLogoId = logoId || (!logoId && !sloganId ? legacyId : "");
  const appliedSloganId = sloganId || (!logoId && !sloganId ? legacyId : "");
  const parts = [];
  if (appliedLogoId) parts.push(`${templateName(appliedLogoId)} Logo`);
  if (appliedSloganId) parts.push(t("brand.sloganMaterialName", "品牌口号与业务落款"));
  return parts.join(" · ");
}

function applyBrandCardDecoration(card: HTMLElement): void {
  // Remove a previous decoration so re-renders stay clean.
  const old = card.querySelector(".brand-card-actions");
  if (old) old.remove();

  const result = brandingForCard(card);
  const task = result?.task || state.previewTask;
  const badge = brandingBadgeForTask(task);
  // Only inject the actions block when branding is relevant to this task.
  const brandingEnabled = !!task?.branding_status && task.branding_status !== "disabled";
  if (!result && !brandingEnabled) return;

  const branding = result?.branding;
  const completed = branding && branding.status === "completed";
  const brandedDownloadUrl = completed
    ? `/api/tasks/${task.task_id}/outputs/${result.index}/branding/download`
    : "";

  const block = document.createElement("div");
  block.className = "brand-card-actions prompt-action-row";
  const layerSummary = brandingLayerSummaryForTask(task, branding);
  block.innerHTML = `
    ${badge}
    ${completed ? `<button type="button" class="brand-toggle" data-brand-toggle="" aria-pressed="true">${t("brand.branded", "品牌版")}</button>` : ""}
    ${completed ? `<a class="brand-download-link" href="${brandedDownloadUrl}" download="" data-brand-download="">${t("brand.downloadBranded", "下载品牌版")}</a>` : ""}
    ${(task?.branding_status === "failed" || task?.branding_status === "partial_failed")
      ? `<button type="button" class="brand-recompose" data-brand-recompose-task="${task.task_id}">${t("brand.recompose", "重新合成")}</button>` : ""}
  `;
  if (layerSummary) {
    const summary = document.createElement("span");
    summary.className = "brand-layer-summary";
    summary.textContent = layerSummary;
    const badgeElement = block.querySelector(".brand-badge");
    if (badgeElement) badgeElement.after(summary);
    else block.prepend(summary);
  }
  card.appendChild(block);

  if (completed) {
    wireToggle(card, branding);
    wireDownload(brandedDownloadUrl, block);
  }
  const recompose = block.querySelector<HTMLButtonElement>("[data-brand-recompose-task]");
  if (recompose) recompose.addEventListener("click", onRecompose);
}

/** Toggle the card's main image + existing download link between branded/raw. */
function wireToggle(card: HTMLElement, branding: any): void {
  const toggle = card.querySelector<HTMLButtonElement>("[data-brand-toggle]");
  const img = card.querySelector<HTMLImageElement>("img[data-lightbox-url]");
  const rawDownload = card.querySelector<HTMLAnchorElement>("[data-download-output-url]");
  if (!toggle || !img) return;
  const rawUrl = String(card.dataset.previewOutputUrl || "");
  const brandedUrl = branding.url || (branding.file ? `/outputs/${branding.file}` : rawUrl);
  let branded = true;
  const apply = () => {
    const url = branded ? brandedUrl : rawUrl;
    img.src = url;
    img.dataset.lightboxUrl = url;
    if (rawDownload) rawDownload.href = url;
    toggle.textContent = branded ? t("brand.branded", "品牌版") : t("brand.raw", "原始底图");
    toggle.setAttribute("aria-pressed", String(branded));
  };
  apply();
  toggle.addEventListener("click", (event) => {
    event.preventDefault();
    branded = !branded;
    apply();
  });
}

function wireDownload(url: string, block: HTMLElement): void {
  const link = block.querySelector<HTMLAnchorElement>("[data-brand-download]");
  if (link) link.href = url;
}

async function onRecompose(event: Event): Promise<void> {
  const button = event.currentTarget as HTMLButtonElement;
  const taskId = button.dataset.brandRecomposeTask || "";
  if (!taskId) return;
  button.disabled = true;
  const original = button.textContent;
  button.textContent = t("brand.recomposing", "合成中…");
  try {
    const response = await fetch(`/api/tasks/${taskId}/branding/recompose`, { method: "POST" });
    if (!response.ok) throw new Error(`recompose failed: ${response.status}`);
    // The response carries the outcome; a render will follow via the next SSE.
  } catch (error) {
    button.disabled = false;
    button.textContent = original;
    console.error(error);
  }
}

function decorateAllCards(): void {
  if (!els.previewGrid) return;
  // The pending flag dedupes back-to-back mutation bursts.
  if (decorateAllCardsPending) return;
  decorateAllCardsPending = true;
  window.requestAnimationFrame(() => {
    decorateAllCardsPending = false;
    const cards = els.previewGrid.querySelectorAll(".preview-card[data-preview-card-key]") as NodeListOf<HTMLElement>;
    cards.forEach(applyBrandCardDecoration);
  });
}
let decorateAllCardsPending = false;

export function initBrandResultActionsFeature(): void {
  if (bound || !els.previewGrid) return;
  bound = true;
  observer = new MutationObserver(() => decorateAllCards());
  observer.observe(els.previewGrid, { childList: true, subtree: false, attributes: true, attributeFilter: ["data-preview-output-url"] });
  // Also refresh when the selected task changes (new preview task rendered).
  decorateAllCards();
}
