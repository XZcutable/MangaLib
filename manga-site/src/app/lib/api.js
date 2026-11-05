// Client for the myMangaLib /api/v1 JSON API.
// serverUrl "" means the same origin, used by the web build and the Vite dev proxy.
// API paths (including the cover_url / image_url the server returns) are relative to the server's base.

import { BASE_PATH } from "./base"
import { reportRestarting, RESTART_CODES } from "./serverStatus"

// "" = the server this page came from, at the path it's served at (BASE_PATH)
let serverUrl = ""
let token = null
let onUnauthorized = () => {}
let onUsernameChangeRequired = () => {}

export function configure(options) {
  if ("server" in options) serverUrl = options.server ?? ""
  if ("token" in options) token = options.token
  if ("onUnauthorized" in options) onUnauthorized = options.onUnauthorized
  if ("onUsernameChangeRequired" in options) onUsernameChangeRequired = options.onUsernameChangeRequired
}

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message)
    this.status = status
    this.code = code
  }
}

// "192.168.1.5:5000/" -> "http://192.168.1.5:5000"
export function normalizeServerUrl(input) {
  let url = (input || "").trim()
  if (!url) return ""
  if (!/^https?:\/\//i.test(url)) url = `http://${url}`
  return url.replace(/\/+$/, "").replace(/\/api\/v1$/, "")
}

async function request(path, { method = "GET", body, signal, server } = {}) {
  const headers = { Accept: "application/json" }
  if (body !== undefined) headers["Content-Type"] = "application/json"
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${serverBase(server ?? serverUrl)}/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error.name === "AbortError") throw error
    throw new ApiError(0, "network", "Can't reach the server")
  }

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized()
    // An admin flagged the account while the app was open
    if (data?.error?.code === "username_change_required") onUsernameChangeRequired()
    // The server is restarting into an update (or still starting); the overlay waits for it
    if (response.status === 503 && RESTART_CODES[data?.error?.code]) reportRestarting(RESTART_CODES[data.error.code])
    throw new ApiError(
      response.status,
      data?.error?.code ?? "error",
      data?.error?.message ?? `Request failed (${response.status})`,
    )
  }
  return data
}

// The server stores dates like "2026-11-02 22:31:00.123456+00:00". Safari can't parse the space or
// microseconds, so convert to standard ISO first.
export function parseServerDate(value) {
  if (!value) return null
  return new Date(value.replace(" ", "T").replace(/(\.\d{3})\d+/, "$1"))
}

// Image URLs from the API are paths. <img> can't send headers, so the token goes in the query.
export function imageUrl(path) {
  if (!path) return ""
  const separator = path.includes("?") ? "&" : "?"
  return `${serverBase()}${path}${token ? `${separator}t=${encodeURIComponent(token)}` : ""}`
}

// Where the server's paths start: the saved server address, or this site's own base path
export function serverBase(server = serverUrl) {
  return server || BASE_PATH
}

const query = (params) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value)
  }
  const text = search.toString()
  return text ? `?${text}` : ""
}

export const api = {
  serverInfo: (server) => request("/server/info", { server }),

  login: (username, password, device) =>
    request("/auth/login", { method: "POST", body: { username, password, device } }),
  register: (username, password) =>
    request("/auth/register", { method: "POST", body: { username, password } }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/auth/me"),
  tokens: () => request("/auth/tokens"),
  revokeToken: (id) => request(`/auth/tokens/${id}`, { method: "DELETE" }),

  list: (list, { offset, limit, sort } = {}, signal) =>
    request(`/manga${query({ list, offset, limit, sort })}`, { signal }),
  search: (q, { offset, limit, sort } = {}, signal) =>
    request(`/manga/search${query({ q, offset, limit, sort })}`, { signal }),
  random: (unread = false) => request(`/manga/random${unread ? "?unread=1" : ""}`),
  manga: (id, signal) => request(`/manga/${id}`, { signal }),
  chapter: (id, chapter, signal) => request(`/manga/${id}/chapters/${chapter}`, { signal }),
  saveProgress: (id, chapter, page) =>
    request(`/manga/${id}/progress`, { method: "PUT", body: { chapter, page } }),
  setState: (id, state) => request(`/manga/${id}/state`, { method: "PUT", body: state }),
  suggestMetadata: (id, changes) =>
    request(`/manga/${id}/metadata/suggestions`, { method: "POST", body: { changes } }),
  withdrawSuggestion: (id) => request(`/manga/${id}/metadata/suggestions/mine`, { method: "DELETE" }),
  setChaptersRead: (id, chapters, is_read) =>
    request(`/manga/${id}/chapters/state`, { method: "PUT", body: { chapters, is_read } }),
  tags: () => request("/tags"),

  // Account
  changePassword: (current_password, new_password) =>
    request("/auth/password", { method: "PUT", body: { current_password, new_password } }),
  changeUsername: (username) => request("/auth/username", { method: "PUT", body: { username } }),

  // Admin
  users: () => request("/admin/users"),
  updateUser: (id, changes) => request(`/admin/users/${id}`, { method: "PUT", body: changes }),
  deleteUser: (id) => request(`/admin/users/${id}`, { method: "DELETE" }),
  createTag: (tag, nsfw) => request("/tags", { method: "POST", body: { tag, nsfw } }),
  deleteTag: (tag) => request(`/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),
  setMangaTags: (id, tags) => request(`/manga/${id}/tags`, { method: "PUT", body: { tags } }),
  editManga: (id, changes) => request(`/manga/${id}`, { method: "PATCH", body: changes }),
  suggestions: () => request("/admin/metadata/suggestions"),
  reviewSuggestion: (id, approve) =>
    request(`/admin/metadata/suggestions/${id}/${approve ? "approve" : "reject"}`, { method: "POST" }),
  job: (id) => request(`/admin/jobs/${id}`),

  // Owner
  deleteManga: (id) => request(`/manga/${id}`, { method: "DELETE" }),
  rescanManga: (id) => request(`/manga/${id}/rescan`, { method: "POST" }),
  crunchManga: (id, chapters) => request(`/manga/${id}/crunch`, { method: "POST", body: chapters ? { chapters } : {} }),
  unpackManga: (id, chapters) => request(`/manga/${id}/unpack`, { method: "POST", body: chapters ? { chapters } : {} }),
  moveManga: (id, libraryPath) => request(`/manga/${id}/move`, { method: "POST", body: { library_path: libraryPath } }),
  library: () => request("/library"),
  addLibraryPath: (path) => request("/library/paths", { method: "POST", body: { path } }),
  // The folder's files are now at `to`: points its manga there (nothing on disk changes)
  moveLibraryPath: (from, to) => request("/library/paths", { method: "PUT", body: { from, to } }),
  removeLibraryPath: (path) =>
    request(`/library/paths${query({ path })}`, { method: "DELETE" }),
  browseFolders: (dir) => request(`/library/browse${query({ dir })}`),
  scanLibrary: (path) => request("/library/scan", { method: "POST", body: path ? { path } : {} }),
  serverConfig: () => request("/server/config"),
  updateServerConfig: (changes) => request("/server/config", { method: "PUT", body: changes }),
  serverUpdate: () => request("/admin/server/update"),
  checkServerUpdate: () => request("/admin/server/update/check", { method: "POST" }),
  downloadServerUpdate: () => request("/admin/server/update/download", { method: "POST" }),
  applyServerUpdate: () => request("/admin/server/update/apply", { method: "POST" }),
  discardServerUpdate: () => request("/admin/server/update", { method: "DELETE" }),
}
