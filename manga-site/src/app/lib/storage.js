import { Capacitor } from "@capacitor/core"
import { Preferences } from "@capacitor/preferences"

// In the mobile app Preferences uses native storage, which the OS won't clear like webview storage.
// In a browser it falls back to localStorage.
export const isNative = Capacitor.isNativePlatform()

export async function getItem(key) {
  const { value } = await Preferences.get({ key })
  return value
}

export async function setItem(key, value) {
  if (value === null || value === undefined) {
    await Preferences.remove({ key })
  } else {
    await Preferences.set({ key, value })
  }
}

// Small synchronous settings (theme, reader direction). Losing these is harmless.
export function getLocal(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

export function setLocal(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Storage can be unavailable (private mode). The setting just won't persist.
  }
}
