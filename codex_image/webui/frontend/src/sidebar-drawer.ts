// Mobile sidebar drawer: hamburger button toggles the sidebar as a slide-in panel on narrow viewports.
// On desktop (>1180px) the toggle is hidden and this is a no-op.

let initialized = false;

function isMobileLayout(): boolean {
  return window.matchMedia("(max-width: 1180px)").matches;
}

function setDrawerOpen(open: boolean): void {
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarDrawerBackdrop");
  const toggle = document.getElementById("sidebarDrawerToggle");
  if (!sidebar || !backdrop || !toggle) return;

  if (open) {
    sidebar.classList.add("sidebar-drawer-open", "is-open");
    backdrop.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
  } else {
    sidebar.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    // Keep sidebar-drawer-open class until transition ends so the slide-out animates;
    // remove it after the transition to restore the collapsed top-bar layout.
    const cleanup = () => {
      sidebar.classList.remove("sidebar-drawer-open");
      backdrop.hidden = true;
      sidebar.removeEventListener("transitionend", cleanup);
    };
    sidebar.addEventListener("transitionend", cleanup);
    // Safety fallback in case transitionend does not fire.
    window.setTimeout(() => {
      if (!sidebar.classList.contains("is-open")) {
        sidebar.classList.remove("sidebar-drawer-open");
        backdrop.hidden = true;
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
    }
    if (backdrop) backdrop.hidden = true;
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }
}

/** Close when a task is selected (so navigating picks the task and returns to the workspace). */
function handleSidebarClick(event: Event): void {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  // Any task card / new-task / filter click should close the drawer.
  if (target.closest("[data-task-id], .task-card, #newTaskButton, .task-filter-button")) {
    closeDrawer();
  }
}

/** Close on Escape. */
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") closeDrawer();
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
