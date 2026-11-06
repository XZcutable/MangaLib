// Registers the service worker (src/sw.js) that lets the web app be installed and open offline.
// Never in the Android app, which ships its own files, and only in built versions.
// When a new version is waiting (the server was updated), a message offers to reload instead of
// reloading by itself, which could interrupt someone reading.
import { Workbox } from "workbox-window"
import { toast } from "sonner"
import { isNative } from "./storage"

const UPDATE_CHECK_INTERVAL = 60 * 60 * 1000

export function registerServiceWorker() {
  if (isNative || import.meta.env.DEV || !("serviceWorker" in navigator) || !window.isSecureContext) return
  // Relative to the <base> tag, so the worker's scope is the path the app is served at
  const workbox = new Workbox(new URL("sw.js", document.baseURI).href, { scope: "./" })

  workbox.addEventListener("waiting", () => {
    // Reloads once the new version has taken over
    workbox.addEventListener("controlling", () => window.location.reload())
    toast("A new version of the app is ready", {
      duration: Infinity,
      action: { label: "Reload", onClick: () => workbox.messageSkipWaiting() },
    })
  })

  workbox.register().catch(() => {
    // Without the worker the app still works; it just can't be installed or open offline
  })

  let lastCheck = Date.now()
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible" || Date.now() - lastCheck < UPDATE_CHECK_INTERVAL) return
    lastCheck = Date.now()
    workbox.update().catch(() => {})
  })
}
