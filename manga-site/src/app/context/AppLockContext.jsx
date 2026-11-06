import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"
import { App } from "@capacitor/app"
import { toast } from "sonner"
import {
  authenticate,
  canUseAppLock,
  DEFAULT_SETTINGS,
  loadLockSettings,
  lockAvailability,
  saveLockSettings,
  setLockedFlag,
  setSecure,
} from "../lib/appLock"
import { useAuth } from "./AuthContext"

const AppLockContext = createContext(undefined)

// locked: "pending" (settings still loading), true or false
export function AppLockProvider({ children }) {
  const { siteName } = useAuth()
  const siteNameRef = useRef(siteName)
  siteNameRef.current = siteName
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [locked, setLocked] = useState(canUseAppLock ? "pending" : false)
  const [error, setError] = useState(null)
  const settingsRef = useRef(settings)
  settingsRef.current = settings
  const lockedRef = useRef(locked)
  lockedRef.current = locked
  // The PIN/pattern screen is its own Android activity, so asking pauses and resumes the app.
  // Those state changes must not lock it again.
  const authenticating = useRef(false)
  const backgroundedAt = useRef(null)

  useEffect(() => {
    setLockedFlag(locked === true || locked === "pending")
  }, [locked])

  const update = useCallback(async (changes) => {
    const next = { ...settingsRef.current, ...changes }
    setSettings(next)
    await saveLockSettings(next)
    return next
  }, [])

  useEffect(() => {
    setSecure(settings.hideInRecents)
  }, [settings.hideInRecents])

  // Asks for the phone's unlock. Returns true on success.
  const ask = useCallback(async (title) => {
    if (authenticating.current) return false
    authenticating.current = true
    setError(null)
    try {
      await authenticate(title)
      return true
    } catch (failure) {
      setError(failure)
      return false
    } finally {
      // Resume arrives slightly after the prompt closes
      setTimeout(() => {
        authenticating.current = false
      }, 500)
    }
  }, [])

  const unlock = useCallback(async () => {
    // The phone's screen lock was removed: there is nothing to unlock with, so turn the lock off
    const { available } = await lockAvailability()
    if (!available) {
      await update({ enabled: false })
      setLocked(false)
      toast("App lock was turned off because this phone has no screen lock.")
      return
    }
    if (await ask(`Unlock ${siteNameRef.current}`)) setLocked(false)
  }, [ask, update])

  useEffect(() => {
    if (!canUseAppLock) return
    let canceled = false
    loadLockSettings().then((loaded) => {
      if (canceled) return
      setSettings(loaded)
      setLocked(loaded.enabled)
    })
    return () => {
      canceled = true
    }
  }, [])

  // Ask as soon as the lock screen shows while the app is on screen
  useEffect(() => {
    if (locked !== true) return
    App.getState()
      .then(({ isActive }) => isActive && unlock())
      .catch(() => {})
  }, [locked, unlock])

  useEffect(() => {
    if (!canUseAppLock) return
    const listener = App.addListener("appStateChange", ({ isActive }) => {
      const { enabled, delayMinutes } = settingsRef.current
      if (!enabled || authenticating.current) return
      if (!isActive) {
        backgroundedAt.current = Date.now()
        // Lock now, so the content is already covered when the user comes back
        if (delayMinutes === 0) setLocked(true)
        return
      }
      if (lockedRef.current === true) {
        unlock()
        return
      }
      const away = backgroundedAt.current === null ? 0 : Date.now() - backgroundedAt.current
      backgroundedAt.current = null
      if (away >= delayMinutes * 60 * 1000) setLocked(true)
    })
    return () => listener.then((handle) => handle.remove())
  }, [unlock])

  // Turning the lock on or off needs a successful unlock first, so nobody locks themselves out
  const setEnabled = useCallback(
    async (on) => {
      const { available, message } = await lockAvailability()
      if (!available) {
        // Nothing to unlock with, so turning it off can't need an unlock
        if (!on) await update({ enabled: false })
        else toast.error(message)
        return !on
      }
      if (!(await ask(on ? "Turn on app lock" : "Turn off app lock"))) return false
      await update({ enabled: on })
      return true
    },
    [ask, update],
  )

  const setDelay = useCallback((delayMinutes) => update({ delayMinutes }), [update])
  const setHideInRecents = useCallback((hideInRecents) => update({ hideInRecents }), [update])

  return (
    <AppLockContext.Provider value={{ settings, locked, error, unlock, setEnabled, setDelay, setHideInRecents }}>
      {children}
    </AppLockContext.Provider>
  )
}

export function useAppLock() {
  const context = useContext(AppLockContext)
  if (!context) throw new Error("useAppLock must be used inside AppLockProvider")
  return context
}
