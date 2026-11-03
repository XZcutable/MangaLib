// App updates for the Android app, published as APKs on GitHub Releases.
// The browser version updates with the server, so none of this runs there.
import { Capacitor, registerPlugin } from "@capacitor/core"
import { App } from "@capacitor/app"
import { getLocal, setLocal } from "./storage"

const ApkUpdater = registerPlugin("ApkUpdater")

export const RELEASES_PAGE = "https://github.com/XZcutable/MangaLib/releases"
// Can be pointed elsewhere for testing a release before publishing it
const LATEST_RELEASE_URL =
  import.meta.env.VITE_UPDATE_URL || "https://api.github.com/repos/XZcutable/MangaLib/releases/latest"

export const canSelfUpdate = Capacitor.getPlatform() === "android"

const AUTO_CHECK_KEY = "updates.autoCheck"
const LAST_CHECK_KEY = "updates.lastCheck"
const SKIPPED_KEY = "updates.skipped"
export const CHECK_EVERY_MS = 6 * 60 * 60 * 1000

export const autoCheckEnabled = () => getLocal(AUTO_CHECK_KEY, "true") === "true"
export const setAutoCheck = (on) => setLocal(AUTO_CHECK_KEY, on ? "true" : "false")
export const skippedVersion = () => getLocal(SKIPPED_KEY, "")
export const skipVersion = (version) => setLocal(SKIPPED_KEY, version)
export const checkIsDue = () => Date.now() - Number(getLocal(LAST_CHECK_KEY, "0")) > CHECK_EVERY_MS

export class UpdateError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

// "v1.10.0" vs "1.9.2": compares number by number. Returns > 0 when a is newer.
export function compareVersions(a, b) {
  const parts = (version) => String(version).replace(/^v/i, "").split(/[.-]/).map((part) => parseInt(part, 10) || 0)
  const [x, y] = [parts(a), parts(b)]
  for (let index = 0; index < Math.max(x.length, y.length); index++) {
    const difference = (x[index] ?? 0) - (y[index] ?? 0)
    if (difference) return difference
  }
  return 0
}

export async function currentVersion() {
  if (!Capacitor.isNativePlatform()) return null
  const info = await App.getInfo()
  return info.version
}

// The latest published release, or null when this version is current
export async function checkForUpdate() {
  const installed = await currentVersion()
  let response
  try {
    response = await fetch(LATEST_RELEASE_URL, { headers: { Accept: "application/vnd.github+json" } })
  } catch {
    throw new UpdateError("network", "Couldn't reach GitHub to check for updates")
  }
  setLocal(LAST_CHECK_KEY, String(Date.now()))
  if (response.status === 404) return null // No releases published yet
  if (!response.ok) throw new UpdateError("check_failed", `Update check failed (${response.status})`)

  const release = await response.json()
  const version = String(release.tag_name ?? "").replace(/^v/i, "")
  const apk = (release.assets ?? []).find((asset) => asset.name?.toLowerCase().endsWith(".apk"))
  if (!version || !apk || compareVersions(version, installed) <= 0) return null

  return {
    version,
    installed,
    notes: release.body?.trim() ?? "",
    url: apk.browser_download_url,
    fileName: apk.name,
    size: apk.size,
    // GitHub publishes a checksum for each file ("sha256:…"); the download is compared against it
    sha256: apk.digest?.startsWith("sha256:") ? apk.digest.slice("sha256:".length).toLowerCase() : null,
    page: release.html_url,
  }
}

export async function downloadUpdate(update, onProgress) {
  const listener = await ApkUpdater.addListener("downloadProgress", ({ received, total }) =>
    onProgress?.(total > 0 ? received / total : null),
  )
  try {
    const { path, sha256 } = await ApkUpdater.download({ url: update.url, fileName: update.fileName })
    if (update.sha256 && sha256 !== update.sha256) {
      throw new UpdateError("checksum", "The download was damaged or changed on the way. Try again.")
    }
    return path
  } catch (error) {
    if (error instanceof UpdateError) throw error
    throw new UpdateError(error.code ?? "download_failed", error.message)
  } finally {
    listener.remove()
  }
}

export async function canInstall() {
  const { allowed } = await ApkUpdater.canInstall()
  return allowed
}

export const openInstallSettings = () => ApkUpdater.openInstallSettings()

export async function installUpdate(path) {
  try {
    await ApkUpdater.install({ path })
  } catch (error) {
    throw new UpdateError(error.code ?? "install_failed", error.message)
  }
}
