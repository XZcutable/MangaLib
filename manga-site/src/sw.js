// Service worker for the installed web app (never registered in the Android app; see lib/pwa.js).
// - Keeps a copy of the app (index.html and the built files) so it opens without the server.
// - Pages of the app: from the server first; the stored index.html only when the server can't be reached.
//   Every answer the server gives, even an error or the 503 page while it updates, is passed on as is.
// - <scope>__offline/...: chapters downloaded in the browser (lib/offlineWeb.js), from Cache Storage.
// - The API, the classic UI and /static are left alone, so they behave exactly as without a worker.
import { cleanupOutdatedCaches, matchPrecache, precache } from "workbox-precaching"

const OFFLINE_CACHE = "mymangalib-offline" // keep in step with lib/offlineWeb.js
const NAVIGATION_TIMEOUT = 4000

precache(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// "/" or "/manga/" behind a proxy at a sub-path
const scope = new URL(self.registration.scope).pathname
const PASS_THROUGH = new Set(["api", "classic", "static"])

// The app shows the "New version" message and asks for this when the user picks Reload
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting()
})
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()))

async function offlineFile(request) {
  const cache = await caches.open(OFFLINE_CACHE)
  const url = new URL(request.url)
  return (await cache.match(url.origin + url.pathname)) ?? new Response("Not downloaded", { status: 404 })
}

async function appPage(request) {
  const network = fetch(request)
  network.catch(() => {}) // Handled below; this only stops a late failure being reported as unhandled
  const timeout = new Promise((resolve) => setTimeout(resolve, NAVIGATION_TIMEOUT, null))
  try {
    // A slow server still wins if the stored copy is missing
    const response = await Promise.race([network, timeout])
    if (response) return response
    return (await matchPrecache("index.html")) ?? (await network)
  } catch {
    const stored = await matchPrecache("index.html")
    if (stored) return stored
    throw new Error("Offline and the app isn't stored yet")
  }
}

async function appFile(request) {
  return (await matchPrecache(request.url)) ?? fetch(request)
}

self.addEventListener("fetch", (event) => {
  const { request } = event
  if (request.method !== "GET") return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin || !url.pathname.startsWith(scope)) return
  if (PASS_THROUGH.has(url.pathname.slice(scope.length).split("/")[0])) return
  // The manifest carries the owner's site name; always ask the server
  if (url.pathname === `${scope}manifest.webmanifest`) return

  if (url.pathname.startsWith(`${scope}__offline/`)) {
    event.respondWith(offlineFile(request))
  } else if (request.mode === "navigate") {
    event.respondWith(appPage(request))
  } else {
    event.respondWith(appFile(request))
  }
})
