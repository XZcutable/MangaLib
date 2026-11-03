// Client for the myMangaLib /api/v1 JSON API.
// serverUrl "" means the same origin, used by the web build and the Vite dev proxy.

let serverUrl = ""
let token = null
let onUnauthorized = () => {}

export function configure(options) {
  if ("server" in options) serverUrl = options.server ?? ""
  if ("token" in options) token = options.token
  if ("onUnauthorized" in options) onUnauthorized = options.onUnauthorized
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
    response = await fetch(`${server ?? serverUrl}/api/v1${path}`, {
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
  return `${serverUrl}${path}${token ? `${separator}t=${encodeURIComponent(token)}` : ""}`
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
  tags: () => request("/tags"),

  // Account
  changePassword: (current_password, new_password) =>
    request("/auth/password", { method: "PUT", body: { current_password, new_password } }),
  changeUsername: (username) => request("/auth/username", { method: "PUT", body: { username } }),

  // Admin
  users: () => request("/admin/users"),
  updateUser: (id, changes) => request(`/admin/users/${id}`, { method: "PUT", body: changes }),
  createTag: (tag, nsfw) => request("/tags", { method: "POST", body: { tag, nsfw } }),
  deleteTag: (tag) => request(`/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),
  setMangaTags: (id, tags) => request(`/manga/${id}/tags`, { method: "PUT", body: { tags } }),
  editManga: (id, changes) => request(`/manga/${id}`, { method: "PATCH", body: changes }),

  // Owner
  deleteManga: (id) => request(`/manga/${id}`, { method: "DELETE" }),
  rescanManga: (id) => request(`/manga/${id}/rescan`, { method: "POST" }),
  library: () => request("/library"),
  addLibraryPath: (path) => request("/library/paths", { method: "POST", body: { path } }),
  removeLibraryPath: (path) =>
    request(`/library/paths${query({ path })}`, { method: "DELETE" }),
  browseFolders: (dir) => request(`/library/browse${query({ dir })}`),
  scanLibrary: (path) => request("/library/scan", { method: "POST", body: path ? { path } : {} }),
  serverConfig: () => request("/server/config"),
  updateServerConfig: (changes) => request("/server/config", { method: "PUT", body: changes }),
}
