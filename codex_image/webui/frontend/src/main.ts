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
  const bindEvents = () => {
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

  openBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openModal();
  });
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
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindEvents);
  } else {
    bindEvents();
  }
}


// --- Enterprise Auth & Dashboard System ---
function initEnterpriseSystem() {
  const bindEvents = () => {
    let currentUser: any = null;

    const userDisplayName = document.getElementById("userDisplayName");
    const userRoleBadge = document.getElementById("userRoleBadge");
    const authActionBtn = document.getElementById("authActionBtn");
    const userProfileBtn = document.getElementById("userProfileBtn");
    const openDashboardBtn = document.getElementById("openDashboardBtn");
    const runBtn = document.getElementById("runButton");
    runBtn?.addEventListener("click", (e) => {
      if (!currentUser) {
        e.preventDefault();
        e.stopPropagation();
        alert("请先登录企业账号后再开始生图！");
        openAuthModal(false);
      }
    }, true);

    const authModal = document.getElementById("authModal");
    const authModalClose = document.getElementById("authModalClose");
    const authTabLogin = document.getElementById("authTabLogin");
    const authTabRegister = document.getElementById("authTabRegister");
    const authForm = document.getElementById("authForm") as HTMLFormElement | null;
    const authModalTitle = document.getElementById("authModalTitle");
    const authUsername = document.getElementById("authUsername") as HTMLInputElement | null;
    const authDisplayName = document.getElementById("authDisplayName") as HTMLInputElement | null;
    const authDisplayNameField = document.getElementById("authDisplayNameField");
    const authPassword = document.getElementById("authPassword") as HTMLInputElement | null;
    const authSubmitBtn = document.getElementById("authSubmitBtn");

    const dashboardModal = document.getElementById("dashboardModal");
    const dashboardModalClose = document.getElementById("dashboardModalClose");
    const dashboardTitle = document.getElementById("dashboardTitle");
    const dashboardSubtitle = document.getElementById("dashboardSubtitle");
    const metricTotalTasks = document.getElementById("metricTotalTasks");
    const metricCompletedTasks = document.getElementById("metricCompletedTasks");
    const metricSuccessRate = document.getElementById("metricSuccessRate");
    const dashboardRatioContainer = document.getElementById("dashboardRatioContainer");
    const dashboardLeaderboardSection = document.getElementById("dashboardLeaderboardSection");
    const dashboardLeaderboardList = document.getElementById("dashboardLeaderboardList");
    const dashboardUserListSection = document.getElementById("dashboardUserListSection");
    const dashboardUserTable = document.getElementById("dashboardUserTable");

    let isRegisterMode = false;

    const updateAuthUI = (user: any) => {
      currentUser = user;
      if (user) {
        if (userDisplayName) userDisplayName.textContent = user.display_name || user.username;
        if (userRoleBadge) {
          userRoleBadge.classList.remove("hidden");
          const isAdmin = user.role === "admin";
          userRoleBadge.textContent = isAdmin ? "管理员" : "员工";
          userRoleBadge.classList.toggle("admin-role", isAdmin);
          if (isAdmin && openUserManagerBtn) openUserManagerBtn.classList.remove("hidden");
          else if (openUserManagerBtn) openUserManagerBtn.classList.add("hidden");
        }
        if (authActionBtn) {
          authActionBtn.querySelector("span")!.textContent = "退出";
        }
      } else {
        if (userDisplayName) userDisplayName.textContent = "未登录";
        if (userRoleBadge) userRoleBadge.classList.add("hidden");
        if (authActionBtn) {
          authActionBtn.querySelector("span")!.textContent = "登录";
        }
      }
    };

    const checkCurrentUser = async () => {
      try {
        const res = await fetch("/api/auth/me");
        const data = await res.json();
        updateAuthUI(data.user);
      } catch {
        updateAuthUI(null);
      }
    };

    const openAuthModal = (register = false) => {
      isRegisterMode = register;
      authModal?.classList.remove("hidden");
      if (isRegisterMode) {
        authTabRegister?.classList.add("active");
        authTabLogin?.classList.remove("active");
        if (authModalTitle) authModalTitle.textContent = "📝 新员工账号注册";
        authDisplayNameField?.classList.remove("hidden");
        if (authSubmitBtn) authSubmitBtn.textContent = "注册并登录";
      } else {
        authTabLogin?.classList.add("active");
        authTabRegister?.classList.remove("active");
        if (authModalTitle) authModalTitle.textContent = "🔐 内部账号登录";
        authDisplayNameField?.classList.add("hidden");
        if (authSubmitBtn) authSubmitBtn.textContent = "立即登录";
      }
      authUsername?.focus();
    };

    const closeAuthModal = () => {
      authModal?.classList.add("hidden");
    };

    authTabLogin?.addEventListener("click", () => openAuthModal(false));
    authTabRegister?.addEventListener("click", () => openAuthModal(true));
    authModalClose?.addEventListener("click", closeAuthModal);
    authModal?.addEventListener("click", (e) => {
      if (e.target === authModal) closeAuthModal();
    });

    authActionBtn?.addEventListener("click", async () => {
      if (currentUser) {
        if (confirm("确定要退出登录吗？")) {
          await fetch("/api/auth/logout", { method: "POST" });
          updateAuthUI(null);
          window.location.reload();
        }
      } else {
        openAuthModal(false);
      }
    });

    userProfileBtn?.addEventListener("click", () => {
      if (!currentUser) openAuthModal(false);
      else openDashboard();
    });

    authForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const u = authUsername?.value.trim() || "";
      const p = authPassword?.value.trim() || "";
      const d = authDisplayName?.value.trim() || "";
      if (!u || !p) return;

      const endpoint = isRegisterMode ? "/api/auth/register" : "/api/auth/login";
      const payload: any = { username: u, password: p };
      if (isRegisterMode) payload.display_name = d;

      if (authSubmitBtn) {
        authSubmitBtn.setAttribute("disabled", "true");
        authSubmitBtn.textContent = "处理中...";
      }

      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "操作失败");
        updateAuthUI(data.user);
        closeAuthModal();
        alert(isRegisterMode ? `欢迎加入团队，${data.user.display_name}！` : `登录成功，欢迎回来 ${data.user.display_name}！`);
        window.location.reload();
      } catch (err: any) {
        alert(err.message || "登录/注册失败");
      } finally {
        if (authSubmitBtn) {
          authSubmitBtn.removeAttribute("disabled");
          authSubmitBtn.textContent = isRegisterMode ? "注册并登录" : "立即登录";
        }
      }
    });

    // 看板逻辑
        const historyBtn = document.getElementById("historyLink");
    historyBtn?.addEventListener("click", (e) => {
      if (!currentUser) {
        e.preventDefault();
        e.stopPropagation();
        alert("生图历史为内部保密数据，请先登录企业账号！");
        openAuthModal(false);
      }
    }, true);

    const openDashboard = async () => {
      if (!currentUser) {
        openAuthModal(false);
        return;
      }
      dashboardModal?.classList.remove("hidden");
      try {
        const res = await fetch("/api/analytics/dashboard");
        const data = await res.json();
        const stats = data.stats || {};
        const isAdmin = data.scope === "enterprise_admin";

        if (dashboardTitle) {
          dashboardTitle.textContent = isAdmin ? "📊 团队生图统计大盘" : `📈 个人生图周报/看板 (${currentUser.display_name})`;
        }
        if (dashboardSubtitle) {
          dashboardSubtitle.textContent = isAdmin ? "全公司生成效率、使用趋势与员工排行榜" : "你的个人创作效率与出图偏好统计";
        }

        if (metricTotalTasks) metricTotalTasks.textContent = String(stats.total_generations || 0);
        if (metricCompletedTasks) metricCompletedTasks.textContent = String(stats.completed_generations || 0);
        if (metricSuccessRate) metricSuccessRate.textContent = `${stats.success_rate || 100}%`;

        if (dashboardRatioContainer) {
          const ratios: any[] = stats.ratio_distribution || [];
          if (!ratios.length) {
            dashboardRatioContainer.innerHTML = `<div class="feedback-empty-state">暂无比例统计数据</div>`;
          } else {
            dashboardRatioContainer.innerHTML = ratios.map((r) => `
              <div class="ratio-pill-item">
                <span>比例 ${r.ratio || "9:16"}</span>
                <strong>${r.count} 次</strong>
              </div>
            `).join("");
          }
        }

        if (isAdmin) {
          dashboardLeaderboardSection?.classList.remove("hidden");
          dashboardUserListSection?.classList.remove("hidden");

          if (dashboardLeaderboardList) {
            const list: any[] = stats.leaderboard || [];
            dashboardLeaderboardList.innerHTML = list.map((item, idx) => `
              <div class="leaderboard-row">
                <span><b>#${idx + 1}</b> ${item.display_name} (@${item.username})</span>
                <strong>${item.task_count} 次</strong>
              </div>
            `).join("");
          }

          if (dashboardUserTable) {
            const users: any[] = stats.users || [];
            dashboardUserTable.innerHTML = `
              <div class="user-table-row" style="font-weight:bold; background: transparent;">
                <span>账号</span><span>姓名</span><span>角色</span><span>注册时间</span>
              </div>
            ` + users.map((u) => `
              <div class="user-table-row">
                <span>${u.username}</span>
                <span>${u.display_name}</span>
                <span>${u.role === "admin" ? "★ 管理员" : "普通员工"}</span>
                <span>${u.created_at}</span>
              </div>
            `).join("");
          }
        } else {
          dashboardLeaderboardSection?.classList.add("hidden");
          dashboardUserListSection?.classList.add("hidden");
        }
      } catch {
        alert("获取统计数据失败");
      }
    };

    openDashboardBtn?.addEventListener("click", openDashboard);
    dashboardModalClose?.addEventListener("click", () => dashboardModal?.classList.add("hidden"));
    const openUserManagerBtn = document.getElementById("openUserManagerBtn");
    const userManagerModal = document.getElementById("userManagerModal");
    const userManagerModalClose = document.getElementById("userManagerModalClose");
    const userManageTableBody = document.getElementById("userManageTableBody");
    const userTotalBadge = document.getElementById("userTotalBadge");
    const newMemberUsername = document.getElementById("newMemberUsername") as HTMLInputElement | null;
    const newMemberDisplayName = document.getElementById("newMemberDisplayName") as HTMLInputElement | null;
    const newMemberPassword = document.getElementById("newMemberPassword") as HTMLInputElement | null;
    const newMemberRole = document.getElementById("newMemberRole") as HTMLSelectElement | null;
    const newMemberSubmitBtn = document.getElementById("newMemberSubmitBtn");

    const loadUserManagerList = async () => {
      if (!userManageTableBody) return;
      try {
        const res = await fetch("/api/admin/users");
        const data = await res.json();
        const users: any[] = data.users || [];
        if (userTotalBadge) userTotalBadge.textContent = `${users.length} 人`;
        if (!users.length) {
          userManageTableBody.innerHTML = `<tr><td colspan="6" style="text-align:center;">暂无员工</td></tr>`;
          return;
        }
        userManageTableBody.innerHTML = users.map((u) => {
          const isSelf = u.id === currentUser?.id;
          return `
            <tr>
              <td><strong>${u.display_name}</strong></td>
              <td>${u.username}</td>
              <td><span class="user-role-badge ${u.role === "admin" ? "admin-role" : ""}">${u.role === "admin" ? "管理员" : "普通员工"}</span></td>
              <td>${u.task_count || 0} 次</td>
              <td style="color:var(--text-secondary); font-size:11px;">${u.created_at}</td>
              <td>
                <div class="user-action-btns">
                  <button class="ghost-button user-reset-btn" data-reset-user="${u.id}">重置密码</button>
                  ${!isSelf ? `<button class="ghost-button user-danger-btn" data-delete-user="${u.id}" data-user-name="${u.display_name}">删除</button>` : `<span style="font-size:11px;color:var(--text-secondary);">(当前账号)</span>`}
                </div>
              </td>
            </tr>
          `;
        }).join("");
      } catch {
        userManageTableBody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#ef4444;">获取成员列表失败</td></tr>`;
      }
    };

    const openUserManager = () => {
      if (!currentUser || currentUser.role !== "admin") {
        alert("仅管理员有权访问用户管理中心");
        return;
      }
      userManagerModal?.classList.remove("hidden");
      void loadUserManagerList();
    };

    openUserManagerBtn?.addEventListener("click", openUserManager);
    userManagerModalClose?.addEventListener("click", () => userManagerModal?.classList.add("hidden"));
    userManagerModal?.addEventListener("click", (e) => {
      if (e.target === userManagerModal) userManagerModal?.classList.add("hidden");
    });

    newMemberSubmitBtn?.addEventListener("click", async () => {
      const u = newMemberUsername?.value.trim() || "";
      const d = newMemberDisplayName?.value.trim() || "";
      const p = newMemberPassword?.value.trim() || "Htai@123456";
      const role = newMemberRole?.value || "employee";
      if (!u) {
        alert("请输入工号/账号名");
        newMemberUsername?.focus();
        return;
      }
      newMemberSubmitBtn.setAttribute("disabled", "true");
      try {
        const res = await fetch("/api/admin/users/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: u, display_name: d, password: p, role }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "创建失败");
        alert(`账号 ${u} 开通成功！`);
        if (newMemberUsername) newMemberUsername.value = "";
        if (newMemberDisplayName) newMemberDisplayName.value = "";
        if (newMemberPassword) newMemberPassword.value = "";
        await loadUserManagerList();
      } catch (err: any) {
        alert(err.message || "创建失败");
      } finally {
        newMemberSubmitBtn.removeAttribute("disabled");
      }
    });

    userManageTableBody?.addEventListener("click", async (e: Event) => {
      const target = e.target as HTMLElement | null;
      const delBtn = target?.closest<HTMLElement>("[data-delete-user]");
      if (delBtn) {
        const uid = delBtn.dataset.deleteUser;
        const uname = delBtn.dataset.userName || "该员工";
        if (confirm(`确定要注销并删除员工 [${uname}] 吗？`)) {
          const res = await fetch(`/api/admin/users/${uid}/delete`, { method: "POST" });
          if (res.ok) {
            alert("已成功删除该员工");
            await loadUserManagerList();
          } else {
            alert("删除失败");
          }
        }
        return;
      }

      const resetBtn = target?.closest<HTMLElement>("[data-reset-user]");
      if (resetBtn) {
        const uid = resetBtn.dataset.resetUser;
        const newPwd = prompt("请输入为该员工设置的新密码（不少于6位）：", "Htai@123456");
        if (!newPwd) return;
        const res = await fetch(`/api/admin/users/${uid}/reset-password`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password: newPwd }),
        });
        if (res.ok) alert("密码重置成功！");
        else alert("重置失败");
      }
    });

    dashboardModal?.addEventListener("click", (e) => {
      if (e.target === dashboardModal) dashboardModal?.classList.add("hidden");
    });

    void checkCurrentUser();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindEvents);
  } else {
    bindEvents();
  }
}


// --- Universal Radio-Group Click Delegation Handler ---
function initUniversalRadioButtons() {
  document.addEventListener("click", (event: Event) => {
    const target = event.target as HTMLElement | null;
    const button = target?.closest<HTMLButtonElement>(".radio-btn");
    if (!button) return;

    const group = button.closest<HTMLElement>(".radio-group");
    if (!group) return;

    const val = button.dataset.val;
    if (val === undefined) return;

    // 1. 切换按钮 active 状态
    group.querySelectorAll(".radio-btn").forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");

    // 2. 联动查找并触发对应的 select 或 input
    const select = group.parentElement?.querySelector<HTMLSelectElement>("select");
    if (select && select.value !== val) {
      select.value = val;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      select.dispatchEvent(new Event("input", { bubbles: true }));
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
initUniversalRadioButtons();
initFeedbackFeature();
initEnterpriseSystem();

window.__codexImageWebUI?.boot();
