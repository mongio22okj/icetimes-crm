// Service worker — offline shell + push notification receiver.
//
// Two cache buckets:
//   apex-shell-{{ cache_version }}   — pre-cached app shell (HTML + CSS + JS)
//   apex-runtime-{{ cache_version }} — runtime stash for static assets
//
// Strategy:
//   - HTML navigations: network-first, fall back to cached shell, then /offline/
//   - Static assets:    cache-first with background revalidate
//   - Other:            pass-through (don't intercept API/HTMX calls)
//
// Push events: receive a JSON payload with {title, body, url} and show
// a system notification. Clicking it opens or focuses the URL.
// Wires into Phase 13's PushSubscription model server-side.

const VERSION = "{{ cache_version }}";
const SHELL_CACHE   = `apex-shell-${VERSION}`;
const RUNTIME_CACHE = `apex-runtime-${VERSION}`;

const SHELL_URL    = "{{ shell_url }}";
const OFFLINE_URL  = "{{ offline_url }}";

// Files pre-cached on install. Keep this list short — the shell HTML
// itself is fetched at install time below.
const PRECACHE = [
  OFFLINE_URL,
  {% for asset in precache_assets %}"{{ asset }}",{% endfor %}
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(PRECACHE)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Clear old version caches so updates take effect.
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((k) => !k.endsWith(VERSION))
        .map((k) => caches.delete(k)),
    )),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Don't intercept WebSocket upgrades, /admin/, /api/, /ws/.
  if (
    url.pathname.startsWith("/admin/") ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/ws/")
  ) return;

  // HTML navigations — network-first.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Stash a copy of the shell so we can fall back next time.
          if (response.ok && url.pathname === SHELL_URL) {
            const copy = response.clone();
            caches.open(SHELL_CACHE).then((c) => c.put(SHELL_URL, copy));
          }
          return response;
        })
        .catch(() =>
          caches.match(request)
            .then((cached) => cached || caches.match(OFFLINE_URL)),
        ),
    );
    return;
  }

  // Static assets — cache-first with background revalidation.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetchPromise = fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(RUNTIME_CACHE).then((c) => c.put(request, copy));
          }
          return response;
        });
        return cached || fetchPromise;
      }),
    );
  }
});

// ── Web Push (Phase 13 wires this up server-side via PushSubscription) ──

self.addEventListener("push", (event) => {
  let payload = { title: "Apex", body: "You have a new notification.", url: "/" };
  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch (_e) { /* swallow malformed payloads */ }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
      data: { url: payload.url },
      tag: payload.tag || "apex-notification",
      renotify: false,
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true })
      .then((windows) => {
        // Focus an existing tab if one's already on the target URL.
        for (const win of windows) {
          if (win.url.endsWith(targetUrl) && "focus" in win) return win.focus();
        }
        return self.clients.openWindow(targetUrl);
      }),
  );
});
