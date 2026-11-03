import { useCallback, useEffect, useState } from "react"
import { FolderPlus, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useAuth } from "../../context/AuthContext"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"
import { FolderPicker } from "./FolderPicker"

const scanSummary = ({ added, updated }) =>
  added || updated
    ? `Scan finished: ${added} new, ${updated} with new chapters`
    : "Scan finished: nothing new"

// Owner only: library folders, scanning and display switches
export function LibrarySection() {
  const s = useStyles()
  const { refreshServerInfo } = useAuth()
  const [paths, setPaths] = useState(null)
  const [config, setConfig] = useState(null)
  const [picking, setPicking] = useState(false)
  const [scanning, setScanning] = useState(null)

  const load = useCallback(() => {
    api.library().then(({ paths }) => setPaths(paths)).catch((error) => toast.error(error.message))
    api.serverConfig().then(setConfig).catch(() => {})
  }, [])
  useEffect(load, [load])

  const scan = async (path) => {
    setScanning(path ?? "all")
    try {
      toast.success(scanSummary(await api.scanLibrary(path)))
    } catch (error) {
      toast.error(error.message)
    } finally {
      setScanning(null)
    }
  }

  const addPath = async (path) => {
    setPicking(false)
    try {
      setPaths((await api.addLibraryPath(path)).paths)
      toast.success("Folder added. Scanning it now…")
      await scan(path)
    } catch (error) {
      toast.error(error.message)
    }
  }

  const removePath = async (path) => {
    if (!confirm(`Stop using "${path}"? Manga already scanned from it stay in the library.`)) return
    try {
      setPaths((await api.removeLibraryPath(path)).paths)
    } catch (error) {
      toast.error(error.message)
    }
  }

  const toggle = async (key) => {
    try {
      setConfig(await api.updateServerConfig({ [key]: !config[key] }))
      refreshServerInfo().catch(() => {})
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <section className={s.card}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className={s.dark ? "text-white" : "text-gray-900"}>Library</h2>
        <div className="flex flex-wrap gap-2">
          <button className={s.button} onClick={() => setPicking(true)}>
            <span className="inline-flex items-center gap-2">
              <FolderPlus className="w-4 h-4" /> Add folder
            </span>
          </button>
          <button
            className={s.primaryButton}
            onClick={() => scan()}
            disabled={scanning !== null || !paths?.length}
          >
            <span className="inline-flex items-center gap-2">
              <RefreshCw className={`w-4 h-4 ${scanning === "all" ? "animate-spin" : ""}`} />
              {scanning === "all" ? "Scanning…" : "Scan all"}
            </span>
          </button>
        </div>
      </div>
      <p className={`text-sm mb-4 ${s.muted}`}>
        Each folder holds one folder or archive per series. Scanning adds new series and new volumes
        to existing ones.
      </p>

      {paths === null ? (
        <p className={s.muted}>Loading…</p>
      ) : paths.length === 0 ? (
        <p className={s.muted}>No folders yet. Add the folder where your manga live.</p>
      ) : (
        <ul className={`border rounded-md divide-y ${s.divider}`}>
          {paths.map((path) => (
            <li key={path} className="flex items-center gap-2 px-3 py-2">
              <span className={`flex-1 min-w-0 truncate font-mono text-sm ${s.text}`}>{path}</span>
              <button
                className={`p-2 rounded-md ${s.muted} hover:text-blue-500`}
                onClick={() => scan(path)}
                disabled={scanning !== null}
                aria-label={`Scan ${path}`}
                title="Scan this folder"
              >
                <RefreshCw className={`w-4 h-4 ${scanning === path ? "animate-spin" : ""}`} />
              </button>
              <button
                className={`p-2 rounded-md ${s.muted} hover:text-red-500`}
                onClick={() => removePath(path)}
                aria-label={`Remove ${path}`}
                title="Remove folder"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {config && (
        <div className="mt-6">
          <h3 className={s.subheading}>Display</h3>
          <div className="flex flex-wrap gap-2">
            <button className={s.chip(config.hide_manga)} onClick={() => toggle("hide_manga")}>
              Hide all pages and covers
            </button>
            <button className={s.chip(config.hide_titles)} onClick={() => toggle("hide_titles")}>
              Hide titles in grids
            </button>
          </div>
          <p className={`text-xs mt-2 ${s.muted}`}>
            For everyone, until the server restarts. Set HIDE_MANGA and HIDE_TITLES in config.toml to
            keep them on.
          </p>
        </div>
      )}

      {picking && <FolderPicker onPick={addPath} onClose={() => setPicking(false)} />}
    </section>
  )
}
