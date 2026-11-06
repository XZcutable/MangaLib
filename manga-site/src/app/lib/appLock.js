// App lock: hides the app behind the phone's own unlock (face, fingerprint or screen lock).
// Android only for now (native AppLockPlugin). An iOS (Face ID) or web (passkey) version only needs to
// provide the same three plugin methods.
import { Capacitor, registerPlugin } from "@capacitor/core"
import { getItem, setItem } from "./storage"

const AppLock = registerPlugin("AppLock")

export const canUseAppLock = Capacitor.getPlatform() === "android"

const SETTINGS_KEY = "appLock"
export const DEFAULT_SETTINGS = { enabled: false, delayMinutes: 0, hideInRecents: false }

export const LOCK_DELAYS = [
  { minutes: 0, label: "Immediately" },
  { minutes: 1, label: "1 minute" },
  { minutes: 5, label: "5 minutes" },
  { minutes: 15, label: "15 minutes" },
]

// Kept in native Preferences, which the OS won't clear like webview storage
export async function loadLockSettings() {
  if (!canUseAppLock) return DEFAULT_SETTINGS
  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse((await getItem(SETTINGS_KEY)) || "{}") }
  } catch {
    return DEFAULT_SETTINGS
  }
}

export const saveLockSettings = (settings) => setItem(SETTINGS_KEY, JSON.stringify(settings))

const UNAVAILABLE_REASONS = {
  none_enrolled: "Set up a screen lock (PIN, pattern, face or fingerprint) in Android settings first.",
  no_hardware: "Set up a screen lock in Android settings first.",
  unavailable: "This phone's screen lock can't be used right now.",
}

// { available, reason, message }
export async function lockAvailability() {
  if (!canUseAppLock) return { available: false, reason: "unavailable", message: UNAVAILABLE_REASONS.unavailable }
  try {
    const { available, reason } = await AppLock.availability()
    return { available, reason, message: available ? null : UNAVAILABLE_REASONS[reason] ?? UNAVAILABLE_REASONS.unavailable }
  } catch {
    return { available: false, reason: "unavailable", message: UNAVAILABLE_REASONS.unavailable }
  }
}

export class LockError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

// Resolves when the user unlocks. Throws LockError with code canceled | lockout | unavailable.
export async function authenticate(title, subtitle) {
  try {
    await AppLock.authenticate({ title, subtitle })
  } catch (error) {
    const code = ["canceled", "lockout", "unavailable"].includes(error?.code) ? error.code : "canceled"
    const message =
      code === "canceled"
        ? "Unlock was canceled."
        : code === "lockout"
          ? error?.message || "Too many attempts. Try again later."
          : UNAVAILABLE_REASONS.unavailable
    throw new LockError(code, message)
  }
}

export function setSecure(on) {
  if (!canUseAppLock) return
  AppLock.setSecure({ on }).catch(() => {})
}

// Read by the back button handler, which lives outside React
let locked = false
export const isLocked = () => locked
export const setLockedFlag = (value) => {
  locked = value
}
