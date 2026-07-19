import { formatTranslation, LOCALE_CHANGE_EVENT, translate } from "./i18n";

let initialized = false;

function selectedLabel(select: HTMLSelectElement | null, fallback: string): string {
  if (!select) return fallback;
  return select.selectedOptions[0]?.textContent?.trim() || select.value || fallback;
}

export function initMobileWorkspaceFeature(): void {
  if (initialized) return;
  initialized = true;

  const dashboard = document.querySelector<HTMLElement>(".dashboard");
  const outputPanel = document.querySelector<HTMLElement>(".output-panel");
  const outputToggle = document.querySelector<HTMLButtonElement>("#mobileOutputSettingsToggle");
  const advancedToggle = document.querySelector<HTMLButtonElement>("#mobileAdvancedSettingsToggle");
  const imagePanel = document.querySelector<HTMLElement>(".image-panel");
  const materialsToggle = document.querySelector<HTMLButtonElement>("#mobileMaterialsToggle");
  const previewGrid = document.querySelector<HTMLElement>("#previewGrid");
  const navActions = document.querySelector<HTMLElement>(".nav-actions");
  const topNav = document.querySelector<HTMLElement>(".top-nav");
  const notificationCenter = document.querySelector<HTMLElement>("#taskNotificationCenter");
  const sidebar = document.querySelector<HTMLElement>(".sidebar");
  const brandActions = sidebar?.querySelector<HTMLElement>(".brand-actions");
  const sidebarFooter = sidebar?.querySelector<HTMLElement>(".sidebar-footer");
  const versionInfo = document.querySelector<HTMLElement>("#versionInfo");
  const navPlaceholder = document.createComment("mobile-nav-placeholder");
  const notificationPlaceholder = document.createComment("mobile-notification-placeholder");
  const versionPlaceholder = document.createComment("mobile-version-placeholder");
  const mobileQuery = window.matchMedia("(max-width: 520px)");
  const compactShellQuery = window.matchMedia("(max-width: 1180px)");

  const setExpanded = (expanded: boolean): void => {
    outputPanel?.classList.toggle("mobile-settings-expanded", expanded);
    outputToggle?.setAttribute("aria-expanded", String(expanded));
    if (outputToggle) outputToggle.textContent = expanded ? "收起" : "展开";
  };

  const setAdvanced = (expanded: boolean): void => {
    outputPanel?.classList.toggle("mobile-advanced-expanded", expanded);
    advancedToggle?.setAttribute("aria-expanded", String(expanded));
    if (advancedToggle) advancedToggle.textContent = expanded ? "收起高级设置" : "高级设置";
  };

  const syncSummary = (): void => {
    const ratio = document.querySelector<HTMLSelectElement>("#ratio");
    const resolution = document.querySelector<HTMLSelectElement>("#resolution");
    const quality = document.querySelector<HTMLSelectElement>("#quality");
    const quantity = document.querySelector<HTMLSelectElement>("#nInput");
    const custom = document.querySelector<HTMLInputElement>("#customSizeToggle")?.checked;
    const set = (id: string, value: string): void => {
      const node = document.querySelector<HTMLElement>(id);
      if (node) node.textContent = value;
    };
    set("#mobileSummaryRatio", custom ? "自定义" : selectedLabel(ratio, "9:16"));
    set("#mobileSummaryResolution", selectedLabel(resolution, "1K").replace("standard", "1K").toUpperCase());
    const qualityText = selectedLabel(quality, "高");
    set("#mobileSummaryQuality", qualityText === "高" ? "高质量" : qualityText);
    set("#mobileSummaryQuantity", `${quantity?.value || "1"} 张`);
  };

  const syncPreviewState = (): void => {
    const hasPreview = Boolean(
      previewGrid?.querySelector(".preview-card, [data-preview-status-card], .waiting-preview, .error-preview"),
    );
    dashboard?.classList.toggle("mobile-has-preview", hasPreview);
  };

  const syncMaterialSummary = (): void => {
    const summary = document.querySelector<HTMLElement>("#mobileMaterialSummary");
    const imageThumbItems = document.querySelector<HTMLElement>("#imageThumbItems");
    const referenceFileSelection = document.querySelector<HTMLElement>("#referenceFileSelection");
    const imageCount = imageThumbItems?.children.length || 0;
    const fileCount = Array.from(referenceFileSelection?.children || []).filter((item) => {
      const element = item as HTMLElement;
      return !element.hidden && !element.classList.contains("hidden");
    }).length;
    const brandCount = document.querySelectorAll("#brandMaterialPicker [aria-checked=\"true\"]").length;
    const count = imageCount + fileCount + brandCount;
    const text = count ? formatTranslation("batch.selectedCount", { count }) : translate("brand.notSelected");
    if (summary && summary.textContent !== text) summary.textContent = text;
  };

  const relocateNav = (): void => {
    if (!navActions || !topNav || !sidebar) return;
    if (mobileQuery.matches) {
      if (navActions.parentNode === topNav) topNav.insertBefore(navPlaceholder, navActions);
      if (notificationCenter?.parentNode === topNav) topNav.insertBefore(notificationPlaceholder, notificationCenter);
      navActions.classList.add("mobile-drawer-tools");
      sidebar.appendChild(navActions);
      if (versionInfo && sidebarFooter) {
        versionInfo.classList.remove("compact-header-version");
        if (versionInfo.parentNode === sidebarFooter) sidebarFooter.insertBefore(versionPlaceholder, versionInfo);
        navActions.appendChild(versionInfo);
      }
      if (notificationCenter) {
        notificationCenter.classList.add("mobile-drawer-notifications");
        sidebar.appendChild(notificationCenter);
      }
      return;
    }
    navActions.classList.remove("mobile-drawer-tools");
    if (navPlaceholder.parentNode) navPlaceholder.parentNode.insertBefore(navActions, navPlaceholder);
    if (notificationCenter) {
      notificationCenter.classList.remove("mobile-drawer-notifications");
      if (notificationPlaceholder.parentNode) {
        notificationPlaceholder.parentNode.insertBefore(notificationCenter, notificationPlaceholder);
      }
    }
    if (versionInfo && compactShellQuery.matches && brandActions) {
      if (versionInfo.parentNode === sidebarFooter) sidebarFooter?.insertBefore(versionPlaceholder, versionInfo);
      versionInfo.classList.add("compact-header-version");
      brandActions.insertBefore(versionInfo, brandActions.firstChild);
    } else if (versionInfo && versionPlaceholder.parentNode) {
      versionInfo.classList.remove("compact-header-version");
      versionPlaceholder.parentNode.insertBefore(versionInfo, versionPlaceholder);
    }
  };

  outputToggle?.addEventListener("click", () => setExpanded(!outputPanel?.classList.contains("mobile-settings-expanded")));
  advancedToggle?.addEventListener("click", () => setAdvanced(!outputPanel?.classList.contains("mobile-advanced-expanded")));
  const setMaterialsExpanded = (expanded: boolean): void => {
    imagePanel?.classList.toggle("mobile-materials-expanded", expanded);
    materialsToggle?.setAttribute("aria-expanded", String(expanded));
  };
  materialsToggle?.addEventListener("click", () => {
    setMaterialsExpanded(!imagePanel?.classList.contains("mobile-materials-expanded"));
  });

  const syncMaterialDisclosure = (): void => {
    if (!mobileQuery.matches) setMaterialsExpanded(false);
  };

  const syncMobileLayout = (): void => {
    syncMaterialDisclosure();
    relocateNav();
  };

  document.addEventListener("input", syncSummary);
  document.addEventListener("change", syncSummary);
  document.addEventListener("input", syncMaterialSummary);
  document.addEventListener("change", syncMaterialSummary);
  document.addEventListener(LOCALE_CHANGE_EVENT, syncMaterialSummary);
  previewGrid && new MutationObserver(syncPreviewState).observe(previewGrid, { childList: true, subtree: true });
  imagePanel && new MutationObserver(syncMaterialSummary).observe(imagePanel, {
    attributes: true,
    attributeFilter: ["aria-checked", "class", "hidden"],
    childList: true,
    subtree: true,
  });
  mobileQuery.addEventListener("change", syncMobileLayout);
  compactShellQuery.addEventListener("change", syncMobileLayout);
  syncSummary();
  syncMaterialSummary();
  syncPreviewState();
  syncMobileLayout();
}
