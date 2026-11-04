import { createContext, useContext, useEffect, useState } from "react"
import { useAuth } from "./AuthContext"
import * as offline from "../lib/offline"

const DownloadsContext = createContext(undefined)

// Shares the offline downloads list with the pages and keeps it up to date while chapters download.
// When the server is reachable it sends progress saved offline and restarts unfinished downloads.
export function DownloadsProvider({ children }) {
  const { status, server } = useAuth()
  const [version, setVersion] = useState(0)
  const [ready, setReady] = useState(!offline.offlineAvailable)

  useEffect(() => offline.subscribe(() => setVersion((value) => value + 1)), [])

  // Wait until the saved server address is known; downloads are kept per server
  useEffect(() => {
    if (status === "loading") return
    offline
      .init()
      .then(offline.loadCurrentServer)
      .then(() => setReady(true))
  }, [status, server])

  useEffect(() => {
    if (status !== "ready" || !ready) return
    offline.flushProgress()
    offline.resume()
    // Coming back to the app after being offline
    const onVisible = () => document.visibilityState === "visible" && offline.flushProgress()
    document.addEventListener("visibilitychange", onVisible)
    return () => document.removeEventListener("visibilitychange", onVisible)
  }, [status, ready])

  const manga = ready ? offline.downloadedManga() : {}
  const hasDownloads = Object.values(manga).some((item) =>
    Object.values(item.chapters).some((chapter) => chapter.state === "done"),
  )

  return (
    <DownloadsContext.Provider value={{ available: offline.offlineAvailable, ready, version, manga, hasDownloads }}>
      {children}
    </DownloadsContext.Provider>
  )
}

export function useDownloads() {
  const context = useContext(DownloadsContext)
  if (context === undefined) throw new Error("useDownloads must be used within a DownloadsProvider")
  return context
}
