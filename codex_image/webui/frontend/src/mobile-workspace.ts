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
  const imageHeading = imagePanel?.querySelector<HTMLElement>(".panel-heading");
  const previewGrid = document.querySelector<HTMLElement>("#previewGrid");
  const navActions = document.querySelector<HTMLElement>(".nav-actions");
  const topNav = document.querySelector<HTMLElement>(".top-nav");
  const notificationCenter = document.querySelector<HTMLElement>("#taskNotificationCenter");
  const sidebar = document.querySelector<HTMLElement>(".sidebar");
  const navPlaceholder = document.createComment("mobile-nav-placeholder");
  const notificationPlaceholder = document.createComment("mobile-notification-placeholder");
  const mobileQuery = window.matchMedia("(max-width: 520px)");

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
    const hasPreview = Boolean(previewGrid?.querySelector(".preview-card, [data-preview-status-card]"));
    dashboard?.classList.toggle("mobile-has-preview", hasPreview);
  };

  const relocateNav = (): void => {
    if (!navActions || !topNav || !sidebar) return;
    if (mobileQuery.matches) {
      if (navActions.parentNode === topNav) topNav.insertBefore(navPlaceholder, navActions);
      if (notificationCenter?.parentNode === topNav) topNav.insertBefore(notificationPlaceholder, notificationCenter);
      navActions.classList.add("mobile-drawer-tools");
      sidebar.appendChild(navActions);
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
  };

  outputToggle?.addEventListener("click", () => setExpanded(!outputPanel?.classList.contains("mobile-settings-expanded")));
  advancedToggle?.addEventListener("click", () => setAdvanced(!outputPanel?.classList.contains("mobile-advanced-expanded")));
  imageHeading?.setAttribute("role", "button");
  imageHeading?.setAttribute("tabindex", "0");
  imageHeading?.setAttribute("aria-expanded", "false");
  const toggleReference = (): void => {
    const expanded = !imagePanel?.classList.contains("mobile-reference-expanded");
    imagePanel?.classList.toggle("mobile-reference-expanded", expanded);
    imageHeading?.setAttribute("aria-expanded", String(expanded));
  };
  imageHeading?.addEventListener("click", toggleReference);
  imageHeading?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    toggleReference();
  });

  document.addEventListener("input", syncSummary);
  document.addEventListener("change", syncSummary);
  previewGrid && new MutationObserver(syncPreviewState).observe(previewGrid, { childList: true, subtree: true });
  mobileQuery.addEventListener("change", relocateNav);
  syncSummary();
  syncPreviewState();
  relocateNav();
}
