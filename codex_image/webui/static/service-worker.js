const CACHE_NAME = "ilab-gpt-conjure-shell-v52";
// Brand/static assets that rarely change: cache-first with background update.
const CACHE_FIRST_PATHS = new Set([
  "/manifest.webmanifest",
  "/static/pwa.js",
  "/static/brand/favicon.svg",
  "/static/brand/pwa-icon-192.png",
  "/static/brand/pwa-icon-512.png",
]);
// Critical resources that iterate frequently (HTML/CSS/JS): network-first so
// every deploy is visible immediately, falling back to cache only when offline.
const NETWORK_FIRST_PATHS = new Set([
  "/",
  "/history",
  "/static/styles.css",
  "/static/app.js",
  "/static/history.js",
]);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll([...CACHE_FIRST_PATHS, ...NETWORK_FIRST_PATHS]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const requestUrl = new URL(request.url);
  if (requestUrl.origin !== self.location.origin) return;

  const pathname = requestUrl.pathname;

  // Navigation requests: always hit the network (HTML is no-store + mtime versioned).
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/", { ignoreSearch: true }))
    );
    return;
  }

  // Critical resources (CSS/JS/HTML): network-first so deploys take effect immediately.
  if (NETWORK_FIRST_PATHS.has(pathname)) {
    event.respondWith(
      fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      }).catch(() => caches.match(request).then((c) => c || caches.match(pathname, { ignoreSearch: true })))
    );
    return;
  }

  // Static brand assets: cache-first with background update.
  if (CACHE_FIRST_PATHS.has(pathname)) {
    event.respondWith(
      caches.match(request).then((cached) => (
        cached || fetch(request).then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        }).catch(() => caches.match(request, { ignoreSearch: true }))
      ))
    );
    return;
  }

  // Anything else: don't intercept — let the browser handle it.
});
