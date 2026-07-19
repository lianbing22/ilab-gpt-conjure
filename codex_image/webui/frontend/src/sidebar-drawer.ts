// Mobile sidebar drawer: hamburger button toggles the sidebar as a slide-in panel on narrow viewports.
// On desktop (>1180px) the toggle is hidden and this is a no-op.

import { translate } from "./i18n";

let initialized = false;
let drawerTrigger: HTMLElement | null = null;

function taskCenterOpenLabel(): string {
  const openLabel = translate("sidebar.openTaskCenter");
  const queueLabel = document.getElementById("queueButton")?.getAttribute("aria-label")?.trim();
  return queueLabel ? `${openLabel} · ${queueLabel}` : openLabel;
}

function isMobileLayout(): boolean {
  return window.matchMedia("(max-width: 1180px)").matches;
}

function setDrawerOpen(open: boolean): void {
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarDrawerBackdrop");
  const toggle = document.getElementById("sidebarDrawerToggle");
  if (!sidebar || !backdrop || !toggle) return;

  if (open) {
    drawerTrigger = document.activeElement instanceof HTMLElement ? document.activeElement : toggle;
    sidebar.classList.add("sidebar-drawer-open", "is-open");
    backdrop.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", translate("sidebar.closeTaskCenter"));
    sidebar.setAttribute("role", "dialog");
    sidebar.setAttribute("aria-modal", "true");
    sidebar.setAttribute("aria-label", translate("sidebar.taskCenter"));
    document.body.classList.add("mobile-task-drawer-open");
    window.setTimeout(() => document.getElementById("taskSearch")?.focus({ preventScroll: true }), 0);
  } else {
    sidebar.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", taskCenterOpenLabel());
    sidebar.removeAttribute("role");
    sidebar.removeAttribute("aria-modal");
    sidebar.removeAttribute("aria-label");
    document.body.classList.remove("mobile-task-drawer-open");
    // Keep sidebar-drawer-open class until transition ends so the slide-out animates;
    // remove it after the transition to restore the collapsed top-bar layout.
    const cleanup = () => {
      sidebar.classList.remove("sidebar-drawer-open");
      backdrop.hidden = true;
      sidebar.removeEventListener("transitionend", cleanup);
      drawerTrigger?.focus?.({ preventScroll: true });
    };
    sidebar.addEventListener("transitionend", cleanup);
    // Safety fallback in case transitionend does not fire.
    window.setTimeout(() => {
      if (!sidebar.classList.contains("is-open")) {
        sidebar.classList.remove("sidebar-drawer-open");
        backdrop.hidden = true;
        sidebar.removeEventListener("transitionend", cleanup);
        drawerTrigger?.focus?.({ preventScroll: true });
      }
    }, 300);
  }
}

function closeDrawer(): void {
  setDrawerOpen(false);
}

function handleToggleClick(): void {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  const isOpen = sidebar.classList.contains("is-open");
  setDrawerOpen(!isOpen);
}

/** Auto-close the drawer when resizing up to desktop layout. */
function handleResize(): void {
  if (!isMobileLayout()) {
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebarDrawerBackdrop");
    const toggle = document.getElementById("sidebarDrawerToggle");
    if (sidebar) {
      sidebar.classList.remove("sidebar-drawer-open", "is-open");
      sidebar.removeAttribute("role");
      sidebar.removeAttribute("aria-modal");
      sidebar.removeAttribute("aria-label");
    }
    if (backdrop) backdrop.hidden = true;
    if (toggle) {
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", taskCenterOpenLabel());
    }
    document.body.classList.remove("mobile-task-drawer-open");
  }
}

/** Close when a task is selected (so navigating picks the task and returns to the workspace). */
function handleSidebarClick(event: Event): void {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  // Selecting a task or starting a new one returns to the workspace.
  if (target.closest("[data-task-id], .task-card, #newTaskButton")) {
    closeDrawer();
  }
}

/** Close on Escape. */
function handleKeydown(event: KeyboardEvent): void {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar?.classList.contains("is-open")) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeDrawer();
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = Array.from(
    sidebar.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href], [tabindex]:not([tabindex='-1'])"),
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

export function initSidebarDrawerFeature(): void {
  if (initialized) return;
  const toggle = document.getElementById("sidebarDrawerToggle");
  const backdrop = document.getElementById("sidebarDrawerBackdrop");
  const sidebar = document.getElementById("sidebar");
  if (!toggle || !backdrop || !sidebar) return;

  // Reveal the toggle (HTML ships it hidden for desktop; JS unhides once wired up so non-JS
  // users on mobile never see a dead button).
  toggle.hidden = false;

  toggle.addEventListener("click", handleToggleClick);
  backdrop.addEventListener("click", closeDrawer);
  sidebar.addEventListener("click", handleSidebarClick);
  window.addEventListener("resize", handleResize);
  window.addEventListener("keydown", handleKeydown);
  initialized = true;
}
