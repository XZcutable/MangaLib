// Passing the Android app between phones without internet (native AppSharePlugin), and backups that
// survive uninstalling it. Only used where canSelfUpdate is true (the Android app).
import { registerPlugin } from "@capacitor/core"
import { Preferences } from "@capacitor/preferences"
import { currentVersion } from "./updater"

const AppShare = registerPlugin("AppShare")

export const BACKUP_KIND = "mymangalib-app-backup"

// Saved logins stay out of backups: the file is saved where other apps can read it.
// Offline downloads stay out too: their pages are deleted with the app.
const SKIPPED_PREFERENCES = [/^token$/, /^offline:/, /^offline-sync:/]

export const shareApp = () => AppShare.shareApp()

// Resolves with what the file is (see AppSharePlugin.inspect), or { cancelled: true }
export const pickApk = () => AppShare.pickApk()

export const uninstallApp = () => AppShare.uninstall()

// What to do with a received APK:
//   invalid    not an app file
//   other-app  a different app
//   same       the version that's installed
//   update     newer and signed with the same key: installs over this one
//   replace    another key or an older version: only installs after uninstalling this one
export function classify(info) {
  if (!info.valid) return "invalid"
  if (!info.samePackage) return "other-app"
  // When Android can't read the signature, try a normal install: the installer itself refuses another key
  const sameKey = info.signatureKnown ? info.sameSigner : null
  if (info.sameVersion && sameKey !== false) return "same"
  if (info.newer && sameKey !== false) return "update"
  return "replace"
}

// "official": signed with the release key. "custom": signed by someone else. "unknown": Android couldn't tell.
export const source = (info) => (!info.signatureKnown ? "unknown" : info.official ? "official" : "custom")

async function collectBackup() {
  const preferences = {}
  const { keys } = await Preferences.keys()
  for (const key of keys) {
    if (SKIPPED_PREFERENCES.some((pattern) => pattern.test(key))) continue
    const { value } = await Preferences.get({ key })
    if (value === null) continue
    if (key === "servers") {
      try {
        const servers = JSON.parse(value).map(({ token, ...entry }) => ({ ...entry, token: null }))
        preferences[key] = JSON.stringify(servers)
      } catch {
        // Unreadable list: leave it out
      }
      continue
    }
    preferences[key] = value
  }
  // Small settings (theme, reader options) live in the WebView's storage
  const local = {}
  for (let index = 0; index < localStorage.length; index++) {
    const key = localStorage.key(index)
    local[key] = localStorage.getItem(key)
  }
  return { kind: BACKUP_KIND, format: 1, appVersion: await currentVersion(), created: new Date().toISOString(), preferences, local }
}

// Saves a backup to a folder the user picks: settings, a copy of this version, and the file about to be
// installed (if any). Resolves with { folder, backup, currentApk, newApk } or { cancelled: true }.
export async function saveBackup({ newApk } = {}) {
  const data = JSON.stringify(await collectBackup(), null, 2)
  return AppShare.backup({ data, newApkPath: newApk?.path, newVersion: newApk?.versionName })
}

// Asks for a backup file and applies it. Servers are merged with the ones already saved (keeping their
// logins); other settings are replaced. Resolves with { servers } (how many came back) or { cancelled: true }.
export async function restoreBackup() {
  const picked = await AppShare.pickBackup()
  if (picked.cancelled) return picked
  let backup
  try {
    backup = JSON.parse(picked.text)
  } catch {
    throw new Error("That file isn't a myMangaLib backup.")
  }
  if (backup?.kind !== BACKUP_KIND || typeof backup.preferences !== "object") {
    throw new Error("That file isn't a myMangaLib backup.")
  }

  let restoredServers = 0
  for (const [key, value] of Object.entries(backup.preferences)) {
    if (typeof value !== "string" || SKIPPED_PREFERENCES.some((pattern) => pattern.test(key))) continue
    if (key === "servers") {
      const current = JSON.parse((await Preferences.get({ key })).value || "[]")
      const known = new Set(current.map((entry) => entry.url))
      const added = JSON.parse(value).filter((entry) => typeof entry?.url === "string" && !known.has(entry.url))
      restoredServers = added.length
      await Preferences.set({ key, value: JSON.stringify([...current, ...added.map((entry) => ({ ...entry, token: null }))]) })
      continue
    }
    // Don't move a logged-in app away from its current server
    if (key === "server" && (await Preferences.get({ key })).value) continue
    await Preferences.set({ key, value })
  }
  for (const [key, value] of Object.entries(backup.local ?? {})) {
    if (typeof value === "string") localStorage.setItem(key, value)
  }
  return { servers: restoredServers }
}
