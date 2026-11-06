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

// Stops the screen dimming while reading
export function keepScreenOn(on) {
  if (!isNative) return
  const call = on ? KeepAwake.keepAwake() : KeepAwake.allowSleep()
  call.catch(() => {})
}
