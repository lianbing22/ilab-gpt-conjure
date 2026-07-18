(() => {
  if (!("serviceWorker" in navigator)) return;
  if (!window.isSecureContext) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).then((reg) => {
      // When a new service worker takes over (e.g. cache version bump), force a
      // single reload so the page picks up the fresh CSS/JS instead of the stale
      // cache the previous worker was serving.
      let refreshing = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (refreshing) return;
        refreshing = true;
        window.location.reload();
      });

      // If a new worker is waiting to activate, tell it to skip waiting so the
      // controllerchange event fires on this same page load.
      reg.addEventListener("updatefound", () => {
        const newWorker = reg.installing;
        if (!newWorker) return;
        newWorker.addEventListener("statechange", () => {
          if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
            newWorker.postMessage("SKIP_WAITING");
          }
        });
      });
    }).catch(() => {
      // PWA support is opportunistic; the WebUI must still work as a normal page.
    });
  });
})();
