import { App } from "@capacitor/app"
import { KeepAwake } from "@capacitor-community/keep-awake"
import { isNative } from "./storage"
import { isLocked } from "./appLock"

// Android back button: go back in the app, and close it from the first screen
export function setupBackButton() {
  if (!isNative) return () => {}
  const listener = App.addListener("backButton", ({ canGoBack }) => {
    // Never navigate behind the lock screen
    if (isLocked()) App.minimizeApp()
    else if (canGoBack) window.history.back()
    else App.exitApp()
  })
  return () => listener.then((handle) => handle.remove())
}

// Opens mymangalib://join?... links (from "Open in the app" on a join page). `open` gets the link.
// A cold start delivers the link both as the launch URL and as an event, so repeats close together are dropped.
export function setupDeepLinks(open) {
  if (!isNative) return () => {}
  let last = { url: null, at: 0 }
  const handle = (url) => {
    if (!url) return
    const now = Date.now()
    if (url === last.url && now - last.at < 3000) return
    last = { url, at: now }
    open(url)
  }
  App.getLaunchUrl()
    .then((result) => handle(result?.url))
    .catch(() => {})
  const listener = App.addListener("appUrlOpen", ({ url }) => handle(url))
  return () => listener.then((handle) => handle.remove())
}

// Stops the screen dimming while reading
export function keepScreenOn(on) {
  if (!isNative) return
  const call = on ? KeepAwake.keepAwake() : KeepAwake.allowSleep()
  call.catch(() => {})
}
