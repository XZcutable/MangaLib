import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"
import { App } from "@capacitor/app"
import {
  autoCheckEnabled,
  canInstall,
  canSelfUpdate,
  checkForUpdate,
  checkIsDue,
  currentVersion,
  downloadUpdate,
  installUpdate,
  openInstallSettings,
  skippedVersion,
  skipVersion,
} from "../lib/updater"
import { UpdateDialog } from "../components/UpdateDialog"

const UpdateContext = createContext(undefined)

// Wait a moment after launch so the update check doesn't compete with loading the library
const STARTUP_DELAY_MS = 4000

// status: idle | checking | available | downloading | needs-permission | installing | error
export function UpdateProvider({ children }) {
  const [version, setVersion] = useState(null)
  const [update, setUpdate] = useState(null)
  const [status, setStatus] = useState("idle")
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)
  const downloaded = useRef(null) // { version, path } so a retry doesn't download again
  const statusRef = useRef(status)
  statusRef.current = status

  useEffect(() => {
    currentVersion().then(setVersion).catch(() => {})
  }, [])

  // Manual checks always report back; automatic ones stay quiet unless there's an update
  // that hasn't been skipped.
  const check = useCallback(async ({ manual = false } = {}) => {
    if (!canSelfUpdate || ["checking", "downloading", "installing"].includes(statusRef.current)) return null
    setStatus("checking")
    setError(null)
    try {
      const found = await checkForUpdate()
      setUpdate(found)
      setStatus(found ? "available" : "idle")
      if (found && (manual || found.version !== skippedVersion())) setOpen(true)
      return found
    } catch (failure) {
      setStatus("idle")
      if (manual) throw failure
      return null
    }
  }, [])

  const install = useCallback(async (path) => {
    if (!(await canInstall())) {
      setStatus("needs-permission")
      return
    }
    setStatus("installing")
    try {
      await installUpdate(path)
      // Android shows its install screen. If the user cancels it, they can try again from here.
      setStatus("available")
    } catch (failure) {
      setError(failure)
      setStatus("error")
    }
  }, [])

  const start = useCallback(async () => {
    if (!update) return
    setError(null)
    try {
      let path = downloaded.current?.version === update.version ? downloaded.current.path : null
      if (!path) {
        setStatus("downloading")
        setProgress(0)
        path = await downloadUpdate(update, setProgress)
        downloaded.current = { version: update.version, path }
      }
      await install(path)
    } catch (failure) {
      setError(failure)
      setStatus("error")
    }
  }, [update, install])

  const allowInstalls = useCallback(() => openInstallSettings(), [])

  // Automatic checks on launch and when the app comes back to the foreground
  useEffect(() => {
    if (!canSelfUpdate) return
    const maybeCheck = () => autoCheckEnabled() && checkIsDue() && check()
    const timer = setTimeout(maybeCheck, STARTUP_DELAY_MS)
    const listener = App.addListener("appStateChange", ({ isActive }) => {
      if (!isActive) return
      // Back from the "Install unknown apps" settings page: carry on with the install
      if (statusRef.current === "needs-permission" && downloaded.current) {
        install(downloaded.current.path)
      } else {
        maybeCheck()
      }
    })
    return () => {
      clearTimeout(timer)
      listener.then((handle) => handle.remove())
    }
  }, [check, install])

  const later = useCallback(() => setOpen(false), [])
  const skip = useCallback(() => {
    if (update) skipVersion(update.version)
    setOpen(false)
  }, [update])

  return (
    <UpdateContext.Provider value={{ supported: canSelfUpdate, version, update, status, check, openDialog: () => setOpen(true) }}>
      {children}
      {open && update && (
        <UpdateDialog
          update={update}
          status={status}
          progress={progress}
          error={error}
          onUpdate={start}
          onAllowInstalls={allowInstalls}
          onLater={later}
          onSkip={skip}
        />
      )}
    </UpdateContext.Provider>
  )
}

export function useUpdates() {
  const context = useContext(UpdateContext)
  if (context === undefined) throw new Error("useUpdates must be used within an UpdateProvider")
  return context
}
