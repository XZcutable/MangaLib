import { useEffect, useState } from "react"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { serverBase } from "../lib/api"
import { subscribeRestarting } from "../lib/serverStatus"
import { Tenma, tenmaArt } from "./Tenma"

const POLL_MS = 2000
const SLOW_AFTER_MS = 3 * 60 * 1000

// Covers the app while the server restarts into an update, then reloads the page the person was on.
export function UpdatingOverlay() {
  const { theme } = useTheme()
  const { siteName } = useAuth()
  const [reason, setReason] = useState(null)
  const [slow, setSlow] = useState(false)

  useEffect(() => subscribeRestarting((next) => setReason((current) => current ?? next)), [])

  // While the server updates, it answers every request with 503, images too. Fetch the picture now so
  // the browser has it cached (assets are cached for a year) by the time the overlay needs it.
  useEffect(() => {
    const image = new Image()
    image.src = tenmaArt("working")
  }, [])

  useEffect(() => {
    if (!reason) return
    let stopped = false
    let timer
    const started = Date.now()
    const poll = async () => {
      try {
        // The supervisor answers 503 while the server is down. The old server still answers 200 for a few
        // seconds after "Apply", with restart_in set, so wait for an answer without it.
        const response = await fetch(`${serverBase()}/api/v1/server/info`, { cache: "no-store" })
        if (response.ok) {
          const info = await response.json()
          if (info.restart_in === null || info.restart_in === undefined) {
            window.location.reload()
            return
          }
        }
      } catch {
        // Between the old server stopping and the supervisor answering; keep waiting
      }
      if (Date.now() - started > SLOW_AFTER_MS) setSlow(true)
      if (!stopped) timer = setTimeout(poll, POLL_MS)
    }
    timer = setTimeout(poll, POLL_MS)
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [reason])

  if (!reason) return null
  const dark = theme === "dark"
  const title = reason === "starting" ? `${siteName} is starting` : `${siteName} is updating`
  return (
    <div
      role="alertdialog"
      aria-live="assertive"
      aria-label={title}
      className={`fixed inset-0 z-[1000] flex items-center justify-center px-4 text-center ${
        dark ? "bg-gray-950 text-gray-100" : "bg-gray-50 text-gray-900"
      }`}
    >
      <div className="max-w-sm">
        <Tenma pose="working" size="h-72 sm:h-96" className="mx-auto mb-4" />
        <div className="mx-auto mb-5 h-8 w-8 animate-spin rounded-full border-4 border-gray-400/40 border-t-brand-600" />
        <h2 className="mb-2 text-xl font-semibold">{title}</h2>
        <p className={dark ? "text-gray-400" : "text-gray-600"}>
          {reason === "starting"
            ? "The server is loading the library."
            : "A new version is being installed. This usually takes under a minute."}{" "}
          You'll be back on this page when it's ready.
        </p>
        {slow && (
          <button
            className="mt-5 rounded-md bg-brand-600 px-4 py-2 text-white hover:bg-brand-700"
            onClick={() => window.location.reload()}
          >
            It's taking a while. Try again
          </button>
        )}
      </div>
    </div>
  )
}
