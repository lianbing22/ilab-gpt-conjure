import "../legacy-app.js";
import { initReferenceFileInputsFeature } from "./reference-file-inputs";
import { initInputSourcesFeature } from "./input-sources";
import { initImageEditorFeature } from "./image-editor";
import { initImageStripFeature } from "./image-strip";
import { initGalleryCategoriesFeature } from "./gallery-categories";
import { initRecentAssetsFeature } from "./recent-assets";
import { initQuickGalleryFeature } from "./quick-gallery";
import { initGalleryGridFeature } from "./gallery-grid";
import { initGalleryItemActionsFeature } from "./gallery-item-actions";
import { initGalleryFeature } from "./gallery";
import { initApiSettingsFeature } from "./api-settings";
import { initApiAdvancedSettingsFeature } from "./api-advanced-settings";
import { initStorageSettingsFeature } from "./storage-settings";
import { initSystemSettingsFeature } from "./system-settings";
import { initColorPaletteFeature } from "./color-palette";
import { initPromptColorsFeature } from "./prompt-colors";
import { initPromptSnippetsFeature } from "./prompt-snippets";
import { initPromptTemplatesFeature } from "./prompt-templates";
import { initPromptFeature } from "./prompt";
import { initPromptFidelityHelpFeature } from "./prompt-fidelity-help";
import { initPromptFindReplaceFeature } from "./prompt-find-replace";
import { initFormControlsFeature } from "./form-controls";
import { initOutputSettingsLockFeature } from "./output-settings-lock";
import { initSidebarDrawerFeature } from "./sidebar-drawer";
import { initMobileWorkspaceFeature } from "./mobile-workspace";
import { initTaskListRenderFeature } from "./task-list-render";
import { initTaskHistoryAnchorsFeature } from "./task-history-anchors";
import { initTaskArchiveControlsFeature } from "./task-archive-controls";
import { initTaskBatchControlsFeature } from "./task-batch-controls";
import { initTaskActionsFeature } from "./task-actions";
import { initTaskSubmitFeature } from "./task-submit";
import { initTaskListControlsFeature } from "./task-list-controls";
import { initTaskListQueueControlsFeature } from "./task-list-queue-controls";
import { initTaskContextMenuFeature } from "./task-context-menu";
import { initTaskNotificationsFeature } from "./task-notifications";
import { initTaskDerivedFeature } from "./task-derived";
import { initTaskPreviewFeature } from "./task-preview";
import { initBrandResultActionsFeature } from "./brand-result-actions";
import { initBrandMaterialsFeature } from "./brand-materials";
import { initTaskFeature } from "./tasks";
import { initTaskSelectionFeature } from "./task-selection";
import { initOverlayPopoversFeature } from "./overlay-popovers";
import { initShellUiFeature } from "./shell-ui";
import { initAppVersionFeature } from "./app-version";
import { initLightboxFeature } from "./lightbox";
import { initializeQueueFeature } from "./queue";
import { initSegmentedIndicatorFeature } from "./segmented-indicator";
import { initI18nFeature } from "./i18n";

initReferenceFileInputsFeature();
initInputSourcesFeature();
initImageEditorFeature();
initImageStripFeature();
initGalleryCategoriesFeature();
initRecentAssetsFeature();
initSidebarDrawerFeature();
initMobileWorkspaceFeature();
initQuickGalleryFeature();
initGalleryGridFeature();
initGalleryItemActionsFeature();
initGalleryFeature();
initApiSettingsFeature();
initApiAdvancedSettingsFeature();
initStorageSettingsFeature();
initSystemSettingsFeature();
initColorPaletteFeature();
initPromptColorsFeature();
initPromptSnippetsFeature();
initPromptTemplatesFeature();
initPromptFeature();
initPromptFidelityHelpFeature();
initPromptFindReplaceFeature();
initFormControlsFeature();
initOutputSettingsLockFeature();
initTaskListRenderFeature();
initTaskHistoryAnchorsFeature();
initTaskArchiveControlsFeature();
initTaskBatchControlsFeature();
initTaskActionsFeature();
initTaskSubmitFeature();
initTaskListControlsFeature();
initTaskListQueueControlsFeature();
initTaskContextMenuFeature();
initTaskNotificationsFeature();
initTaskDerivedFeature();
initTaskPreviewFeature();
initBrandResultActionsFeature();
initBrandMaterialsFeature();
initTaskFeature();
initTaskSelectionFeature();
initOverlayPopoversFeature();
initShellUiFeature();
initI18nFeature();
initAppVersionFeature();
initLightboxFeature();
initializeQueueFeature();
initSegmentedIndicatorFeature();

// --- Desktop Advanced Settings Toggle & Inspiration Card Handlers ---
function initModernUiEnhancements() {
  const bindEvents = () => {
    const toggleBtn = document.getElementById("desktopAdvancedToggle");
    const collapse = document.getElementById("advancedSettingsCollapse");
    const arrow = document.getElementById("desktopAdvancedArrow");

    if (toggleBtn && collapse) {
      toggleBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const isHidden = collapse.classList.contains("hidden");
        if (isHidden) {
          collapse.classList.remove("hidden");
          toggleBtn.setAttribute("aria-expanded", "true");
          if (arrow) arrow.textContent = "▴";
        } else {
          collapse.classList.add("hidden");
          toggleBtn.setAttribute("aria-expanded", "false");
          if (arrow) arrow.textContent = "▾";
        }
      });
    }

    document.addEventListener("click", (event: Event) => {
      const target = event.target as HTMLElement | null;
      const card = target?.closest<HTMLElement>(".inspiration-card");
      if (!card) return;
      const prompt = card.dataset.prompt;
      const ratio = card.dataset.ratio;
      const editor = document.getElementById("promptEditor");
      const hiddenPrompt = document.getElementById("prompt") as HTMLInputElement | null;
      if (prompt && editor) {
        editor.textContent = prompt;
        if (hiddenPrompt) hiddenPrompt.value = prompt;
        const bridge = (window as any).__codexImageWebUI?.bridge;
        bridge?.methods?.updateCharCount?.();
        bridge?.methods?.syncPromptGalleryMentionsFromInputs?.();
        bridge?.methods?.updateRequestPreview?.();
      }
      if (ratio) {
        const selector = "#ratioGroup [data-val=\"" + ratio + "\"]";
        const ratioBtn = document.querySelector<HTMLButtonElement>(selector);
        ratioBtn?.click();
      }
      editor?.focus();
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindEvents);
  } else {
    bindEvents();
  }
}
initModernUiEnhancements();

window.__codexImageWebUI?.boot();
