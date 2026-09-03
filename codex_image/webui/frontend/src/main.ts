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

// --- Feedback Board Handlers ---
function initFeedbackFeature() {
  const modal = document.getElementById("feedbackModal");
  const openBtn = document.getElementById("feedbackButton");
  const closeBtn = document.getElementById("feedbackModalClose");
  const submitBtn = document.getElementById("feedbackSubmitBtn");
  const nicknameInput = document.getElementById("feedbackNickname") as HTMLInputElement | null;
  const contactInput = document.getElementById("feedbackContact") as HTMLInputElement | null;
  const contentInput = document.getElementById("feedbackContent") as HTMLTextAreaElement | null;
  const charNotice = document.getElementById("feedbackCharNotice");
  const countBadge = document.getElementById("feedbackCountBadge");
  const listContainer = document.getElementById("feedbackListContainer");

  if (!modal || !openBtn) return;

  const escapeHtml = (str: string) => {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  };

  const loadFeedbackList = async () => {
    if (!listContainer) return;
    try {
      const res = await fetch("/api/feedback");
      const data = await res.json();
      const messages: any[] = data.messages || [];
      if (countBadge) countBadge.textContent = `${messages.length} 条`;
      if (!messages.length) {
        listContainer.innerHTML = `<div class="feedback-empty-state">暂无留言，快来留下你的第一条建议吧！</div>`;
        return;
      }
      listContainer.innerHTML = messages.map((msg) => {
        const replies: any[] = msg.replies || [];
        const repliesHtml = replies.map((rep) => `
          <div class="feedback-reply-item">
            <div class="feedback-reply-meta">
              <strong class="feedback-admin-badge">★ ${escapeHtml(rep.author || "管理员")}</strong>
              <span class="feedback-reply-time">${escapeHtml(rep.created_at || "")}</span>
            </div>
            <div class="feedback-reply-content">${escapeHtml(rep.content || "")}</div>
          </div>
        `).join("");

        return `
          <div class="feedback-item-card" data-feedback-id="${escapeHtml(msg.id)}">
            <div class="feedback-item-header">
              <div class="feedback-user-info">
                <span class="feedback-avatar">👤</span>
                <strong>${escapeHtml(msg.nickname || "创作者")}</strong>
                ${msg.contact ? `<span class="feedback-contact-tag">${escapeHtml(msg.contact)}</span>` : ""}
              </div>
              <span class="feedback-time">${escapeHtml(msg.created_at || "")}</span>
            </div>
            <div class="feedback-item-body">${escapeHtml(msg.content || "")}</div>
            
            ${replies.length ? `<div class="feedback-replies-wrap">${repliesHtml}</div>` : ""}

            <div class="feedback-item-actions">
              <button class="feedback-reply-trigger" type="button" data-reply-to="${escapeHtml(msg.id)}">💬 回复</button>
            </div>
            <div class="feedback-reply-box hidden" id="replyBox-${escapeHtml(msg.id)}">
              <input type="text" class="control feedback-reply-input" placeholder="输入回复内容..." maxlength="500" />
              <button class="run-button text-sm feedback-reply-submit" type="button" data-reply-submit="${escapeHtml(msg.id)}">发送回复</button>
            </div>
          </div>
        `;
      }).join("");
    } catch {
      if (listContainer) listContainer.innerHTML = `<div class="feedback-empty-state">获取留言列表失败</div>`;
    }
  };

  const openModal = () => {
    modal.classList.remove("hidden");
    void loadFeedbackList();
    window.setTimeout(() => contentInput?.focus(), 50);
  };

  const closeModal = () => {
    modal.classList.add("hidden");
  };

  openBtn.addEventListener("click", openModal);
  closeBtn?.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  contentInput?.addEventListener("input", () => {
    if (charNotice) charNotice.textContent = `${contentInput.value.length} / 1000`;
  });

  submitBtn?.addEventListener("click", async () => {
    const content = contentInput?.value.trim() || "";
    if (!content) {
      alert("请输入留言内容");
      contentInput?.focus();
      return;
    }
    submitBtn.setAttribute("disabled", "true");
    submitBtn.textContent = "提交中...";
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: nicknameInput?.value.trim() || "",
          contact: contactInput?.value.trim() || "",
          content: content,
        }),
      });
      if (!res.ok) throw new Error("提交失败");
      if (contentInput) contentInput.value = "";
      if (charNotice) charNotice.textContent = "0 / 1000";
      await loadFeedbackList();
    } catch (err: any) {
      alert(err?.message || "留言发布失败，请稍后重试");
    } finally {
      submitBtn.removeAttribute("disabled");
      submitBtn.textContent = "发送留言";
    }
  });

  // 回复交互
  listContainer?.addEventListener("click", async (e: Event) => {
    const target = e.target as HTMLElement | null;
    const trigger = target?.closest<HTMLElement>("[data-reply-to]");
    if (trigger) {
      const msgId = trigger.dataset.replyTo;
      const box = document.getElementById(`replyBox-${msgId}`);
      box?.classList.toggle("hidden");
      box?.querySelector<HTMLInputElement>("input")?.focus();
      return;
    }

    const replySubmit = target?.closest<HTMLElement>("[data-reply-submit]");
    if (replySubmit) {
      const msgId = replySubmit.dataset.replySubmit;
      const box = document.getElementById(`replyBox-${msgId}`);
      const input = box?.querySelector<HTMLInputElement>("input");
      const replyContent = input?.value.trim() || "";
      if (!replyContent) return;
      replySubmit.setAttribute("disabled", "true");
      try {
        const res = await fetch(`/api/feedback/${encodeURIComponent(String(msgId))}/reply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            author: "我 (管理员)",
            content: replyContent,
          }),
        });
        if (!res.ok) throw new Error("回复失败");
        await loadFeedbackList();
      } catch (err: any) {
        alert(err?.message || "回复失败");
        replySubmit.removeAttribute("disabled");
      }
    }
  });
}

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
initFeedbackFeature();

window.__codexImageWebUI?.boot();
