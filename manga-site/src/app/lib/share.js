// Links for sharing a server: <server>/join?code=... (opens the Join page in a browser or the app),
// and mymangalib://join?server=...&code=... (opens the Android app straight from a browser).
import { BASE_PATH } from "./base"
import { normalizeServerUrl } from "./api"

export const APP_SCHEME = "mymangalib:"
export const ANDROID_DOWNLOAD_URL = "https://github.com/XZcutable/MangaLib/releases/latest"

// The address to put in links: the owner's public address, the one this app uses, or this site
export function shareBase(serverInfo, server) {
  return (serverInfo?.public_url || server || `${window.location.origin}${BASE_PATH}`).replace(/\/+$/, "")
}

export function joinLink(base, code) {
  return code ? `${base}/join?code=${encodeURIComponent(code)}` : `${base}/join`
}

export function appLink(server, code) {
  const params = new URLSearchParams({ server })
  if (code) params.set("code", code)
  return `mymangalib://join?${params}`
}

// The page in this app that handles a link
export function joinPath({ server, code }) {
  const params = new URLSearchParams()
  if (server) params.set("server", server)
  if (code) params.set("code", code)
  return `/join?${params}`
}

// Who an address works for: "device" (only this phone or computer), "network" (the same Wi-Fi or VPN),
// or "public" (anywhere). Only a guess from the address, to warn before sharing a link that won't work.
export function addressReach(url) {
  let host
  try {
    host = new URL(url).hostname.toLowerCase().replace(/^\[|\]$/g, "")
  } catch {
    return "public"
  }
  // 10.0.2.2 is the computer running the Android emulator
  if (host === "localhost" || host.startsWith("127.") || host === "::1" || host === "10.0.2.2") return "device"
  if (
    /^10\./.test(host) ||
    /^192\.168\./.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host) ||
    /^169\.254\./.test(host) ||
    // Tailscale and other carrier-grade NAT addresses
    /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./.test(host) ||
    /\.(local|lan|home|internal|localdomain)$/.test(host) ||
    !host.includes(".")
  ) {
    return "network"
  }
  return "public"
}

// Reads a scanned or opened link. Returns { server, code } (code may be null), or null when it isn't one.
// Accepts mymangalib://join?server=...&code=..., <server>/join?code=..., and a plain server address.
export function parseJoinLink(text) {
  let url
  try {
    url = new URL((text || "").trim())
  } catch {
    return null
  }
  if (url.protocol === APP_SCHEME) {
    // mymangalib://join?... : "join" is the host
    const server = normalizeServerUrl(url.searchParams.get("server") || "")
    if (url.host !== "join" || !/^https?:\/\//i.test(server)) return null
    return { server, code: url.searchParams.get("code") || null }
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null

  const path = url.pathname.replace(/\/+$/, "")
  if (path.endsWith("/join") || path === "/join") {
    return { server: `${url.origin}${path.slice(0, -"/join".length)}`, code: url.searchParams.get("code") || null }
  }
  // Any other web address is taken as the server itself
  return { server: normalizeServerUrl(`${url.origin}${path}`), code: null }
}
