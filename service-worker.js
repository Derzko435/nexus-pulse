/* NEXUS PULSE service worker */
const VERSION = "v5-2026-09-25";
const SHELL_CACHE = "nexus-pulse-shell-" + VERSION;
const DATA_CACHE = "nexus-pulse-data-" + VERSION;
const FONT_CACHE = "nexus-pulse-fonts-v1";
const KEEP = [SHELL_CACHE, DATA_CACHE, FONT_CACHE];

const SHELL = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./features-extra.js",
  "./guides-content.js",
  "./content-hub.js",
  "./manifest.json",
  "./assets/nexus-pulse-icon.png",
  "./assets/icons/icon-192.png",
  "./assets/icons/icon-512.png",
  "./assets/icons/icon-maskable-192.png",
  "./assets/icons/icon-maskable-512.png",
  "./assets/icons/apple-touch-icon.png",
];

const DATA = [
  "./data/daily.json",
  "./data/deals.json",
  "./data/freebies.json",
  "./data/matches.json",
  "./data/lfg_snapshot.json",
  "./data/ping_targets.json",
  "./data/steam_catalog_snapshot.json",
  "./data/news.json",
  "./data/releases.json",
  "./data/new_games.json",
  "./data/patches.json",
  "./data/videos.json",
  "./data/catalog.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const shell = await caches.open(SHELL_CACHE);
      // cache: "reload" bypasses the HTTP cache so a new SW version gets fresh files
      await shell.addAll(SHELL.map((u) => new Request(u, { cache: "reload" })));
      // data is optional at install time (offline fallback only)
      const data = await caches.open(DATA_CACHE);
      await Promise.all(
        DATA.map((u) =>
          fetch(new Request(u, { cache: "reload" }))
            .then((res) => (res.ok ? data.put(u, res) : null))
            .catch(() => null)
        )
      );
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => !KEEP.includes(k)).map((k) => caches.delete(k)));
      if (self.registration.navigationPreload) {
        try { await self.registration.navigationPreload.enable(); } catch (e) { /* ignore */ }
      }
      await self.clients.claim();
    })()
  );
});

function dataKey(url) {
  // strip cache-busting query (?t=...) so offline fallback matches
  return url.origin + url.pathname;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Google Fonts: stale-while-revalidate (so the offline page keeps its look)
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    event.respondWith(
      caches.open(FONT_CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        const network = fetch(req)
          .then((res) => {
            if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone());
            return res;
          })
          .catch(() => cached || Response.error());
        return cached || network;
      })
    );
    return;
  }

  if (url.origin !== self.location.origin) return;

  // Page navigations: network-first, fallback to cached shell (works for ?cpu=… share links too)
  if (req.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          const preload = await event.preloadResponse;
          const res = preload || (await fetch(req));
          if (res && res.ok) {
            const cache = await caches.open(SHELL_CACHE);
            cache.put("./index.html", res.clone());
          }
          return res;
        } catch (e) {
          const cache = await caches.open(SHELL_CACHE);
          return (
            (await cache.match("./index.html")) ||
            (await cache.match("./")) ||
            Response.error()
          );
        }
      })()
    );
    return;
  }

  // Data JSON: network-first, cache fallback
  if (/\/data\/[^/]+\.json$/i.test(url.pathname)) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(DATA_CACHE);
        try {
          const res = await fetch(req);
          if (res && res.ok) cache.put(dataKey(url), res.clone());
          return res;
        } catch (e) {
          const cached = await cache.match(dataKey(url));
          if (cached) return cached;
          throw e;
        }
      })()
    );
    return;
  }

  // Static shell / assets: stale-while-revalidate
  event.respondWith(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      const cached = await cache.match(req, { ignoreSearch: true });
      const network = fetch(req)
        .then((res) => {
          if (res && res.ok && res.type === "basic") cache.put(req, res.clone());
          return res;
        })
        .catch(() => cached || Response.error());
      if (cached) {
        event.waitUntil(network.catch(() => null));
        return cached;
      }
      return network;
    })()
  );
});
