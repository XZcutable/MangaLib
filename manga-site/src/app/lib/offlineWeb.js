// The browser version of the native Offline plugin (android/.../OfflinePlugin.java), with the same
// methods and events, so lib/offline.js works the same in both. Pages are fetched into Cache Storage
// under <base>/__offline/<folder>/<name>.<ext>; the service worker (src/sw.js) answers those URLs,
// so <img src> shows them offline. Downloads only run while the page is open; offline.js puts
// unfinished ones back in the queue and resume() starts them again.

import { BASE_PATH } from "./base"

export const OFFLINE_CACHE = "mymangalib-offline"
const PREFIX = `${BASE_PATH}/__offline`
const PAGES_AT_ONCE = 3
const SIZE_HEADER = "X-Offline-Size"

// Works over HTTPS (or on localhost) with service workers, which open the saved pages offline
export const webOfflineSupported =
  typeof window !== "undefined" && window.isSecureContext && "serviceWorker" in navigator && "caches" in window

const listeners = { progress: new Set(), complete: new Set(), failed: new Set() }
const emit = (event, data) => listeners[event].forEach((listener) => listener(data))

const queue = []
let current = null

const keyFor = (folder, file) => new URL(`${PREFIX}/${folder}/${file}`, location.origin).href
const folderPrefix = (folder) => keyFor(folder, "")

function extension(contentType) {
  const type = (contentType || "").toLowerCase().split(";")[0].trim()
  return { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "image/avif": "avif" }[type] ?? "img"
}

async function keysIn(cache, folder) {
  const prefix = folderPrefix(folder)
  return (await cache.keys()).filter((request) => request.url.startsWith(prefix))
}

const fileName = (request) => decodeURIComponent(request.url.split("/").pop())

async function downloadPage(cache, folder, name, url, existing) {
  if (existing.some((file) => file.startsWith(`${name}.`))) return
  let response
  try {
    response = await fetch(url, { credentials: "omit" })
  } catch {
    // A server on another address blocks this unless it lists this site in CORS_ORIGINS
    const sameSite = new URL(url, location.href).origin === location.origin
    throw new Error(sameSite ? "Couldn't reach the server" : `The server doesn't allow downloads from ${location.origin}`)
  }
  if (!response.ok) throw new Error(`The server answered ${response.status} for page ${name}`)
  const blob = await response.blob()
  const type = response.headers.get("Content-Type") || blob.type
  await cache.put(
    keyFor(folder, `${name}.${extension(type)}`),
    new Response(blob, { headers: { "Content-Type": type, [SIZE_HEADER]: String(blob.size) } }),
  )
}

async function run(job) {
  const cache = await caches.open(OFFLINE_CACHE)
  const existing = (await keysIn(cache, job.folder)).map(fileName)
  const pages = [...job.pages]
  let failure = null
  const worker = async () => {
    while (pages.length && !job.cancelled && !failure) {
      const page = pages.shift()
      try {
        await downloadPage(cache, job.folder, page.name, page.url, existing)
        job.done++
        if (!job.cancelled) emit("progress", { id: job.id, done: job.done, total: job.pages.length })
      } catch (error) {
        failure ??= error
      }
    }
  }
  await Promise.all(Array.from({ length: PAGES_AT_ONCE }, worker))
  if (failure) throw failure
  return (await keysIn(cache, job.folder)).map(fileName)
}

async function runQueue() {
  if (current) return
  while (queue.length) {
    current = queue.shift()
    try {
      const files = await run(current)
      if (!current.cancelled) emit("complete", { id: current.id, files })
    } catch (error) {
      if (!current.cancelled) emit("failed", { id: current.id, message: error.message || String(error) })
    }
  }
  current = null
}

let persistAsked = false

export const offlineWeb = {
  async info() {
    // root only has to be set; page URLs come from fileUrl() in offline.js
    return { root: PREFIX, active: [current, ...queue].filter(Boolean).map((job) => job.id) }
  },

  addListener(event, listener) {
    listeners[event].add(listener)
    return { remove: () => listeners[event].delete(listener) }
  },

  async enqueue({ id, folder, pages }) {
    if (!persistAsked) {
      persistAsked = true
      // Asks the browser not to clear the downloads when space runs low
      navigator.storage?.persist?.().catch(() => {})
    }
    if (current?.id === id || queue.some((job) => job.id === id)) return
    queue.push({ id, folder, pages, done: 0, cancelled: false })
    runQueue()
  },

  async cancel({ id }) {
    if (current?.id === id) current.cancelled = true
    const index = queue.findIndex((job) => job.id === id)
    if (index >= 0) queue.splice(index, 1)
  },

  async remove({ folder }) {
    const cache = await caches.open(OFFLINE_CACHE)
    await Promise.all((await keysIn(cache, folder)).map((request) => cache.delete(request)))
  },

  async usage({ folder } = {}) {
    const cache = await caches.open(OFFLINE_CACHE)
    const requests = folder ? await keysIn(cache, folder) : await cache.keys()
    let bytes = 0
    for (const request of requests) {
      const response = await cache.match(request)
      bytes += Number(response?.headers.get(SIZE_HEADER)) || 0
    }
    return { bytes }
  },

  // The browser has no download notification to ask for
  async checkPermissions() {
    return { notifications: "granted" }
  },
  async requestPermissions() {
    return { notifications: "granted" }
  },
}
