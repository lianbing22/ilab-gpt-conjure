import { formatTranslation, LOCALE_CHANGE_EVENT, translate } from "./i18n";
import { getLegacyBridge } from "./state";

interface PostUpdateOnboarding {
  kind?: string;
  notice_id?: string;
  from_version_label?: string;
  to_version_label?: string;
  release_url?: string;
  standard_download_url?: string;
}

interface ReleaseHistoryItem {
  version?: string;
  version_label?: string;
  released_at?: string;
  change_ids?: string[];
}

interface AppVersionPayload {
  current_version?: string;
  current_version_label?: string;
  latest_version_label?: string;
  source?: "portable" | "standard_app" | "source" | string;
  update_available?: boolean;
  release_url?: string;
  standard_download_url?: string | null;
  updater_available?: boolean;
  post_update_onboarding?: PostUpdateOnboarding | null;
  release_history?: ReleaseHistoryItem[];
}

let appVersionInitialized = false;
let payload: AppVersionPayload | null = null;
let onboardingAutoShown = false;
let popoverPositionFrame = 0;

function els() {
  return getLegacyBridge().els;
}

function versionPopoverIsOpen(): boolean {
  return !(els().versionModal as HTMLElement | null)?.classList.contains("hidden");
}

function positionVersionPopover(): void {
  popoverPositionFrame = 0;
  const modal = els().versionModal as HTMLElement | null;
  const panel = modal?.querySelector<HTMLElement>(".version-popover-panel") || null;
  const trigger = els().versionInfo as HTMLElement | null;
  if (!modal || !panel || !trigger || !versionPopoverIsOpen()) return;
  if (window.matchMedia("(max-width: 520px)").matches) {
    panel.style.removeProperty("left");
    panel.style.removeProperty("top");
    panel.style.removeProperty("width");
    return;
  }
  const margin = 12;
  const gap = 12;
  const triggerRect = trigger.getBoundingClientRect();
  const viewportWidth = document.documentElement.clientWidth;
  const viewportHeight = document.documentElement.clientHeight;
  const preferredLeft = triggerRect.right + gap;
  const availableRight = viewportWidth - preferredLeft - margin;
  panel.style.removeProperty("width");
  let panelRect = panel.getBoundingClientRect();
  if (availableRight >= 300 && panelRect.width > availableRight) {
    panel.style.width = `${Math.floor(availableRight)}px`;
    panelRect = panel.getBoundingClientRect();
  }
  const fallbackLeft = triggerRect.left - panelRect.width - gap;
  const left = preferredLeft + panelRect.width <= viewportWidth - margin
    ? preferredLeft
    : Math.max(margin, fallbackLeft);
  const top = Math.min(
    Math.max(margin, triggerRect.bottom - panelRect.height),
    Math.max(margin, viewportHeight - panelRect.height - margin),
  );
  panel.style.left = `${Math.round(left)}px`;
  panel.style.top = `${Math.round(top)}px`;
}

function scheduleVersionPopoverPosition(): void {
  if (!versionPopoverIsOpen() || popoverPositionFrame) return;
  popoverPositionFrame = window.requestAnimationFrame(positionVersionPopover);
}

function setModalHidden(hidden: boolean, restoreFocus = hidden): void {
  const modal = els().versionModal as HTMLElement | null;
  if (!modal) return;
  const wasHidden = modal.classList.contains("hidden");
  modal.classList.toggle("hidden", hidden);
  modal.setAttribute("aria-hidden", hidden ? "true" : "false");
  const versionInfo = els().versionInfo as HTMLButtonElement | null;
  versionInfo?.setAttribute("aria-expanded", hidden ? "false" : "true");
  if (!hidden) {
    scheduleVersionPopoverPosition();
  } else {
    const panel = modal.querySelector<HTMLElement>(".version-popover-panel");
    panel?.style.removeProperty("left");
    panel?.style.removeProperty("top");
    panel?.style.removeProperty("width");
    if (!wasHidden && restoreFocus) versionInfo?.focus({ preventScroll: true });
  }
}

function openVersionPopover(): void {
  renderAppVersion();
  setModalHidden(false, false);
  window.requestAnimationFrame(() => {
    positionVersionPopover();
    (els().versionModalClose as HTMLButtonElement | null)?.focus({ preventScroll: true });
  });
}

function renderReleaseHistory(): void {
  const container = els().versionReleaseHistory as HTMLElement | null;
  if (!container) return;
  container.replaceChildren();
  const releases = payload?.release_history || [];
  if (!releases.length) {
    const empty = document.createElement("p");
    empty.className = "version-history-empty";
    empty.textContent = payload ? translate("version.historyEmpty") : translate("version.loading");
    container.appendChild(empty);
    return;
  }
  releases.forEach((release) => {
    const item = document.createElement("article");
    item.className = "version-release-item";
    const heading = document.createElement("div");
    heading.className = "version-release-heading";
    const title = document.createElement("strong");
    title.textContent = release.version_label || release.version || "";
    heading.appendChild(title);
    if (release.version && release.version === payload?.current_version) {
      const current = document.createElement("span");
      current.className = "version-current-badge";
      current.textContent = translate("version.currentBadge");
      heading.appendChild(current);
    }
    if (release.released_at) {
      const date = document.createElement("time");
      date.dateTime = release.released_at;
      date.textContent = formatTranslation("version.releaseDate", { date: release.released_at });
      heading.appendChild(date);
    }
    item.appendChild(heading);
    const changes = document.createElement("ul");
    (release.change_ids || []).forEach((changeId) => {
      const change = document.createElement("li");
      change.textContent = translate(`version.change.${changeId}`);
      changes.appendChild(change);
    });
    item.appendChild(changes);
    container.appendChild(item);
  });
}

function renderAppVersion(statusText?: string): void {
  const versionInfo = els().versionInfo as HTMLButtonElement | null;
  const versionLabel = els().versionLabel as HTMLElement | null;
  const badge = els().versionUpdateBadge as HTMLElement | null;
  const current = els().versionCurrent as HTMLElement | null;
  const latest = els().versionLatest as HTMLElement | null;
  const source = els().versionSource as HTMLElement | null;
  const onboardingNotice = els().versionOnboardingNotice as HTMLElement | null;
  const onboardingBody = els().versionOnboardingBody as HTMLElement | null;
  const releaseLink = els().versionReleaseLink as HTMLAnchorElement | null;
  const standardDownloadLink = els().versionStandardDownloadLink as HTMLAnchorElement | null;
  const updateButton = els().versionUpdateButton as HTMLButtonElement | null;
  const continuePortableButton = els().versionContinuePortableButton as HTMLButtonElement | null;
  const dismissOnboardingButton = els().versionDismissOnboardingButton as HTMLButtonElement | null;
  const modalStatus = els().versionModalStatus as HTMLElement | null;
  const panel = (els().versionModal as HTMLElement | null)?.querySelector(".version-modal-panel") as HTMLElement | null;
  const currentLabel = payload?.current_version_label || "...";
  const latestLabel = payload?.latest_version_label || currentLabel;
  const updateAvailable = Boolean(payload?.update_available);
  const onboarding = payload?.post_update_onboarding || null;
  const onboardingVersion = onboarding?.to_version_label || currentLabel;
  const isPortable = payload?.source === "portable";
  const isStandardApp = payload?.source === "standard_app";
  const standardDownloadUrl =
    onboarding?.standard_download_url ||
    payload?.standard_download_url ||
    "";
  const showStandardDownload = Boolean(onboarding || (isStandardApp && updateAvailable && standardDownloadUrl));
  const updateAvailableText = formatTranslation("footer.updateAvailable", { version: latestLabel });

  if (versionLabel) {
    versionLabel.textContent = payload ? formatTranslation("footer.version", { version: currentLabel }) : translate("footer.versionLoading");
  }
  if (versionInfo) {
    versionInfo.classList.toggle("has-update", updateAvailable);
    versionInfo.title = updateAvailable ? updateAvailableText : translate("footer.versionInfo");
    versionInfo.setAttribute("aria-label", updateAvailable ? updateAvailableText : translate("footer.versionInfo"));
  }
  if (badge) {
    badge.classList.toggle("hidden", !updateAvailable);
    badge.setAttribute("aria-label", translate("footer.updateBadge"));
  }
  if (current) current.textContent = currentLabel;
  if (latest) latest.textContent = latestLabel;
  if (source) {
    source.textContent = runtimeSourceLabel(payload?.source);
  }
  renderReleaseHistory();
  if (releaseLink) {
    releaseLink.href = payload?.release_url || "https://github.com/kadevin/ilab-gpt-conjure/releases";
  }
  if (panel) {
    panel.classList.toggle("has-onboarding", Boolean(onboarding));
  }
  if (onboardingNotice) {
    onboardingNotice.classList.toggle("hidden", !onboarding);
  }
  if (onboardingBody) {
    onboardingBody.textContent = translate("version.onboardingBody");
  }
  if (standardDownloadLink) {
    standardDownloadLink.classList.toggle("hidden", !showStandardDownload);
    standardDownloadLink.href = standardDownloadUrl || onboarding?.release_url || payload?.release_url || "https://github.com/kadevin/ilab-gpt-conjure/releases";
  }
  if (continuePortableButton) {
    continuePortableButton.classList.toggle("hidden", !onboarding);
  }
  if (dismissOnboardingButton) {
    dismissOnboardingButton.classList.toggle("hidden", !onboarding);
  }
  if (updateButton) {
    updateButton.classList.toggle("hidden", !isPortable);
    updateButton.disabled = !(payload?.update_available && payload?.updater_available);
  }
  if (modalStatus) {
    modalStatus.textContent =
      statusText ||
      (onboarding
        ? formatTranslation("version.onboardingStatus", { version: onboardingVersion })
        : updateAvailable
          ? formatTranslation(isStandardApp ? "version.standardUpdateAvailable" : "version.updateAvailable", { version: latestLabel })
          : isStandardApp
            ? translate("version.standardManualInstall")
            : payload?.updater_available === false && !isPortable
            ? translate("version.noUpdater")
            : translate("version.upToDate"));
  }
}

function runtimeSourceLabel(source: AppVersionPayload["source"]): string {
  if (source === "portable") return translate("version.sourcePortable");
  if (source === "standard_app") return translate("version.sourceStandard");
  return translate("version.sourceSource");
}

async function refreshAppVersion(): Promise<void> {
  try {
    const response = await fetch("/api/app-version");
    if (!response.ok) throw new Error(`Version API failed: ${response.status}`);
    payload = await response.json();
  } catch {
    payload = {
      current_version_label: "...",
      latest_version_label: "...",
      source: "source",
      update_available: false,
      updater_available: false,
      release_url: "https://github.com/kadevin/ilab-gpt-conjure/releases",
    };
  }
  renderAppVersion();
  if (payload?.post_update_onboarding && !onboardingAutoShown) {
    onboardingAutoShown = true;
    openVersionPopover();
  }
}

async function openUpdater(): Promise<void> {
  const updateButton = els().versionUpdateButton as HTMLButtonElement | null;
  if (updateButton) updateButton.disabled = true;
  try {
    const response = await fetch("/api/app-version/open-updater", { method: "POST" });
    if (!response.ok) throw new Error(`Updater API failed: ${response.status}`);
    payload = await response.json();
    renderAppVersion(translate("version.updaterStarted"));
  } catch {
    renderAppVersion(translate("version.updaterFailed"));
  }
}

async function dismissOnboarding(closeModal: boolean): Promise<void> {
  try {
    const response = await fetch("/api/app-version/dismiss-onboarding", { method: "POST" });
    if (!response.ok) throw new Error(`Onboarding API failed: ${response.status}`);
    payload = await response.json();
    renderAppVersion();
    if (closeModal) setModalHidden(true);
  } catch {
    renderAppVersion(translate("version.dismissFailed"));
  }
}

function bindAppVersionEvents(): void {
  (els().versionInfo as HTMLElement | null)?.addEventListener("click", (event) => {
    event.stopPropagation();
    openVersionPopover();
  });
  (els().versionModalClose as HTMLElement | null)?.addEventListener("click", () => setModalHidden(true));
  (els().versionModal as HTMLElement | null)?.addEventListener("pointerdown", (event) => {
    if (event.target === els().versionModal) setModalHidden(true);
  });
  (els().versionUpdateButton as HTMLElement | null)?.addEventListener("click", () => {
    void openUpdater();
  });
  (els().versionStandardDownloadLink as HTMLElement | null)?.addEventListener("click", () => {
    if (payload?.post_update_onboarding) void dismissOnboarding(false);
  });
  (els().versionContinuePortableButton as HTMLElement | null)?.addEventListener("click", () => {
    void dismissOnboarding(true);
  });
  (els().versionDismissOnboardingButton as HTMLElement | null)?.addEventListener("click", () => {
    void dismissOnboarding(true);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !versionPopoverIsOpen()) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    setModalHidden(true);
  }, true);
  document.addEventListener("pointermove", scheduleVersionPopoverPosition);
  window.addEventListener("resize", scheduleVersionPopoverPosition);
  window.addEventListener("scroll", scheduleVersionPopoverPosition, true);
  document.addEventListener(LOCALE_CHANGE_EVENT, () => {
    renderAppVersion();
    scheduleVersionPopoverPosition();
  });
}

export function initAppVersionFeature(): void {
  if (appVersionInitialized) return;
  appVersionInitialized = true;
  bindAppVersionEvents();
  renderAppVersion();
  void refreshAppVersion();
}
