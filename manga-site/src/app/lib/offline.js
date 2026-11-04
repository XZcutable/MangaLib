// Offline downloads (Android app only). The native Offline plugin (android/.../OfflinePlugin.java)
// fetches page images into app storage; this module decides what to fetch and remembers what's on
// the phone, per server, in Preferences:
//   { manga: { [id]: { title, cover, info, chapters: { [number]: { state, done, total, files, chapter, error } } } } }
// state is "queued", "downloading", "done" or "failed". files are page file names in page order.
// Reading progress saved while offline is queued and sent when the server answers again.

import { Capacitor, registerPlugin } from "@capacitor/core"
import { api, ApiError, imageUrl, serverBase } from "./api"
import { getItem, setItem, isNative } from "./storage"

const Offline = isNative ? registerPlugin("Offline") : null
export const offlineAvailable = isNative

let root = null // absolute path of the downloads folder on the phone
let manifests = {} // serverKey -> manifest
let listeners = new Set()
let ready = false
let readyPromise = null

// A short, file-name-safe key for the server address (FNV-1a)
function hash(text) {
  let value = 0x811c9dc5
  for (let index = 0; index < text.length; index++) {
    value ^= text.charCodeAt(index)
    value = Math.imul(value, 0x01000193) >>> 0
  }
  return value.toString(36)
}

const serverKey = () => `s${hash(serverBase() || "local")}`
const manifestKey = (key) => `offline:${key}`
const syncKey = (key) => `offline-sync:${key}`
const folderFor = (mangaId, chapter) => `${serverKey()}/m${mangaId}/${chapter === "cover" ? "cover" : `c${chapter}`}`
const jobId = (mangaId, chapter) => `${serverKey()}:${mangaId}:${chapter}`

function manifest() {
  const key = serverKey()
  if (!manifests[key]) manifests[key] = { manga: {} }
  return manifests[key]
}

let saveTimer = null
function changed({ save = true } = {}) {
  listeners.forEach((listener) => listener())
  if (!save) return
  // Progress events come quickly; write the manifest at most every half second
  clearTimeout(saveTimer)
  const key = serverKey()
  const data = manifests[key]
  saveTimer = setTimeout(() => setItem(manifestKey(key), JSON.stringify(data)).catch(() => {}), 500)
}

export function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function parseJobId(id) {
  const [key, mangaId, chapter] = id.split(":")
  return { key, mangaId, chapter }
}

function entryFor(id) {
  const { key, mangaId, chapter } = parseJobId(id)
  const manga = manifests[key]?.manga[mangaId]
  if (!manga) return {}
  return { manga, chapter, entry: chapter === "cover" ? null : manga.chapters[chapter] }
}

let activeJobs = new Set()

// Loads the saved list for the server the app is connected to (again after changing server)
export async function loadCurrentServer() {
  if (!isNative) return
  const key = serverKey()
  if (manifests[key]) return
  try {
    const saved = await getItem(manifestKey(key))
    manifests[key] = saved ? JSON.parse(saved) : { manga: {} }
  } catch {
    manifests[key] = { manga: {} }
  }
  // Downloads the plugin isn't running any more (the app was closed) go back in the queue
  for (const [mangaId, manga] of Object.entries(manifests[key].manga)) {
    for (const [number, entry] of Object.entries(manga.chapters)) {
      if (entry.state === "downloading" && !activeJobs.has(jobId(mangaId, number))) entry.state = "queued"
    }
  }
  changed({ save: false })
}

// Loads the saved list and listens to the plugin. Call once the server address is known.
export function init() {
  if (!isNative) {
    ready = true
    return Promise.resolve()
  }
  if (readyPromise) return readyPromise
  readyPromise = (async () => {
    try {
      const info = await Offline.info()
      root = info.root
      activeJobs = new Set(info.active)
    } catch {
      root = null
    }
    await loadCurrentServer()

    Offline.addListener("progress", ({ id, done, total }) => {
      const { entry } = entryFor(id)
      if (!entry) return
      Object.assign(entry, { state: "downloading", done, total })
      changed({ save: done === total })
    })
    Offline.addListener("complete", ({ id, files }) => {
      const { manga, chapter, entry } = entryFor(id)
      if (!manga) return
      if (chapter === "cover") {
        manga.cover = files.find((name) => name.startsWith("cover.")) ?? null
      } else if (entry) {
        // "12.jpg" -> page 12
        const byPage = Object.fromEntries(files.map((name) => [Number(name.split(".")[0]), name]))
        const ordered = Array.from({ length: entry.total }, (_, index) => byPage[index + 1])
        if (ordered.some((name) => !name)) {
          Object.assign(entry, { state: "failed", error: "Some pages are missing" })
        } else {
          Object.assign(entry, { state: "done", done: entry.total, files: ordered, error: null })
        }
      }
      changed()
    })
    Offline.addListener("failed", ({ id, message }) => {
      const { entry } = entryFor(id)
      if (!entry) return
      Object.assign(entry, { state: "failed", error: message })
      changed()
    })
    ready = true
    changed({ save: false })
  })()
  return readyPromise
}

export const isReady = () => ready

// --- Reading what's downloaded ---

export function downloadedManga() {
  return manifest().manga
}

export function chapterState(mangaId, number) {
  return manifest().manga[mangaId]?.chapters[number] ?? null
}

const fileUrl = (mangaId, chapter, name) =>
  Capacitor.convertFileSrc(`${root}/${folderFor(mangaId, chapter)}/${name}`)

export function coverUrl(mangaId) {
  const manga = manifest().manga[mangaId]
  return manga?.cover && root ? fileUrl(mangaId, "cover", manga.cover) : null
}

// What the reader needs from GET /manga/:id, when the server can't be reached
export function mangaInfo(mangaId) {
  return manifest().manga[mangaId]?.info ?? null
}

// A downloaded chapter shaped like GET /manga/:id/chapters/:n, with local page URLs.
// Previous and next point at downloaded chapters only when `offlineOnly` is set.
export function localChapter(mangaId, number, { offlineOnly = false } = {}) {
  const manga = manifest().manga[mangaId]
  const entry = manga?.chapters[number]
  if (!root || entry?.state !== "done") return null
  const chapter = { ...entry.chapter }
  if (offlineOnly) {
    const downloaded = Object.entries(manga.chapters)
      .filter(([, item]) => item.state === "done")
      .map(([key]) => Number(key))
      .sort((a, b) => a - b)
    chapter.previous_chapter = downloaded.filter((n) => n < number).pop() ?? null
    chapter.next_chapter = downloaded.find((n) => n > number) ?? null
  }
  chapter.pages = entry.files.map((name, index) => ({
    number: index + 1,
    image_url: null,
    local_url: fileUrl(mangaId, number, name),
  }))
  return chapter
}

// --- Downloading ---

let permissionAsked = false
async function askForNotifications() {
  if (permissionAsked) return
  permissionAsked = true
  try {
    const status = await Offline.checkPermissions()
    if (status.notifications === "prompt" || status.notifications === "prompt-with-rationale") {
      await Offline.requestPermissions()
    }
  } catch {
    // Downloads work without it; only the progress notification is hidden
  }
}

async function enqueueChapter(mangaId, number) {
  const manga = manifest().manga[mangaId]
  const entry = manga.chapters[number]
  const chapter = await api.chapter(mangaId, number)
  entry.chapter = {
    manga_id: chapter.manga_id,
    manga_title: chapter.manga_title,
    number: chapter.number,
    title: chapter.title,
    page_count: chapter.page_count,
    previous_chapter: chapter.previous_chapter,
    next_chapter: chapter.next_chapter,
  }
  entry.total = chapter.page_count
  await Offline.enqueue({
    id: jobId(mangaId, number),
    folder: folderFor(mangaId, number),
    title: `${manga.title} · ${chapter.title || `Chapter ${number}`}`,
    pages: chapter.pages.map((page) => ({ name: String(page.number), url: imageUrl(page.image_url) })),
  })
}

// Downloads chapters of a manga (`manga` is the GET /manga/:id response)
export async function download(manga, numbers) {
  await init()
  await askForNotifications()
  const all = manifest().manga
  const saved = (all[manga.id] ??= { title: manga.title, cover: null, chapters: {} })
  saved.title = manga.title
  saved.info = {
    id: manga.id,
    title: manga.title,
    chapters: manga.chapters.map(({ number, title, page_count }) => ({ number, title, page_count })),
    reading_hint: manga.reading_hint ?? null,
  }
  for (const number of numbers) {
    const entry = saved.chapters[number]
    if (entry?.state === "done" || entry?.state === "downloading") continue
    saved.chapters[number] = { state: "queued", done: 0, total: 0, files: null, chapter: null, error: null }
  }
  changed()

  if (!saved.cover && manga.cover_url) {
    Offline.enqueue({
      id: jobId(manga.id, "cover"),
      folder: folderFor(manga.id, "cover"),
      title: manga.title,
      pages: [{ name: "cover", url: imageUrl(manga.cover_url) }],
    }).catch(() => {})
  }

  for (const number of numbers) {
    if (saved.chapters[number]?.state !== "queued") continue
    try {
      await enqueueChapter(manga.id, number)
    } catch (error) {
      Object.assign(saved.chapters[number], { state: "failed", error: error.message })
    }
    changed()
  }
}

// Starts again whatever was queued when the app closed. Needs the server.
export async function resume() {
  await init()
  if (!isNative) return
  for (const [mangaId, manga] of Object.entries(manifest().manga)) {
    for (const [number, entry] of Object.entries(manga.chapters)) {
      if (entry.state !== "queued") continue
      try {
        await enqueueChapter(Number(mangaId), Number(number))
      } catch (error) {
        if (error instanceof ApiError && error.status === 0) return // Still offline
        Object.assign(entry, { state: "failed", error: error.message })
      }
    }
  }
  changed()
}

export async function retry(mangaId, number) {
  const entry = chapterState(mangaId, number)
  if (!entry) return
  Object.assign(entry, { state: "queued", error: null })
  changed()
  try {
    await enqueueChapter(mangaId, number)
  } catch (error) {
    Object.assign(entry, { state: "failed", error: error.message })
    changed()
  }
}

// Removes chapters (or the whole manga when numbers is null) from the phone
export async function remove(mangaId, numbers = null) {
  await init()
  const all = manifest().manga
  const manga = all[mangaId]
  if (!manga) return
  const targets = numbers ?? Object.keys(manga.chapters).map(Number)
  for (const number of targets) {
    await Offline.cancel({ id: jobId(mangaId, number) }).catch(() => {})
    await Offline.remove({ folder: folderFor(mangaId, number) }).catch(() => {})
    delete manga.chapters[number]
  }
  if (numbers === null || Object.keys(manga.chapters).length === 0) {
    await Offline.remove({ folder: `${serverKey()}/m${mangaId}` }).catch(() => {})
    delete all[mangaId]
  }
  changed()
}

export async function usage(mangaId) {
  if (!isNative) return 0
  try {
    const { bytes } = await Offline.usage(
      mangaId === undefined ? {} : { folder: `${serverKey()}/m${mangaId}` },
    )
    return bytes
  } catch {
    return 0
  }
}

// --- Progress made offline ---

// Saves the reader position. Without a connection it's queued: every finished chapter (its last
// page marks it read on the server) and the latest position for each manga.
export async function saveProgress(mangaId, chapter, page, isLastPage = false) {
  try {
    await api.saveProgress(mangaId, chapter, page)
  } catch (error) {
    if (!isNative || !(error instanceof ApiError) || error.status !== 0) return
    const key = syncKey(serverKey())
    const queue = JSON.parse((await getItem(key)) ?? "[]").filter(
      (item) => item.manga !== mangaId || item.last,
    )
    queue.push({ manga: mangaId, chapter, page, last: isLastPage })
    await setItem(key, JSON.stringify(queue))
  }
}

let flushing = false
export async function flushProgress() {
  if (!isNative || flushing) return
  flushing = true
  try {
    const key = syncKey(serverKey())
    const queue = JSON.parse((await getItem(key)) ?? "[]")
    while (queue.length) {
      const item = queue[0]
      try {
        await api.saveProgress(item.manga, item.chapter, item.page)
      } catch (error) {
        if (error instanceof ApiError && error.status === 0) break // Still offline; try later
      }
      queue.shift()
      await setItem(key, JSON.stringify(queue))
    }
  } finally {
    flushing = false
  }
}
