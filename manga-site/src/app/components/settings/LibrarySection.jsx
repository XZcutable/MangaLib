import { useCallback, useEffect, useState } from "react"
import { FolderInput, FolderPlus, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useAuth } from "../../context/AuthContext"
import { useServerFeatures } from "../../lib/features"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"
import { FolderPicker } from "./FolderPicker"
import { SettingSwitch } from "./SettingSwitch"

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
  const [moving, setMoving] = useState(null) // the folder whose new location is being picked
  const features = useServerFeatures()

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

  const moveTo = async (to) => {
    const from = moving
    setMoving(null)
    const message = `Use "${to}" in place of "${from}"? Do this after moving the files there (or mounting them there). The series keep their reading progress. Nothing on disk changes.`
    if (!confirm(message)) return
    try {
      const result = await api.moveLibraryPath(from, to)
      setPaths(result.paths)
      if (result.missing) {
        const examples = result.missing_titles.slice(0, 3).join(", ")
        toast.warning(
          `${result.missing} of ${result.moved} series weren't found in the new folder (e.g. ${examples}). If it's the wrong folder, move it back.`,
          { duration: 15000 },
        )
      } else {
        toast.success(`Folder moved: ${result.moved} series point to ${result.path}`)
      }
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

  const [siteName, setSiteName] = useState("")
  useEffect(() => {
    if (config) setSiteName(config.site_name)
  }, [config?.site_name])

  const saveSiteName = async (event) => {
    event.preventDefault()
    try {
      const updated = await api.updateServerConfig({ site_name: siteName })
      setConfig(updated)
      refreshServerInfo().catch(() => {})
      toast.success(`The site is now called ${updated.site_name}`)
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
                className={`p-2 rounded-md ${s.muted} hover:text-brand-500`}
                onClick={() => scan(path)}
                disabled={scanning !== null}
                aria-label={`Scan ${path}`}
                title="Scan this folder"
              >
                <RefreshCw className={`w-4 h-4 ${scanning === path ? "animate-spin" : ""}`} />
              </button>
              {features.moveFiles && (
                <button
                  className={`p-2 rounded-md ${s.muted} hover:text-brand-500`}
                  onClick={() => setMoving(path)}
                  aria-label={`${path} moved`}
                  title="Moved: point this folder to its new location"
                >
                  <FolderInput className="w-4 h-4" />
                </button>
              )}
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
          <form onSubmit={saveSiteName} className="mb-4">
            <label htmlFor="site-name" className={`block mb-1 ${s.text}`}>
              Site name
            </label>
            <div className="flex flex-wrap gap-2">
              <input
                id="site-name"
                className={`${s.input} flex-1 min-w-[10rem]`}
                value={siteName}
                onChange={(event) => setSiteName(event.target.value)}
                maxLength={40}
                placeholder="myMangaLib"
              />
              <button className={s.button} disabled={siteName.trim() === config.site_name}>
                Save
              </button>
            </div>
            <p className={`text-xs mt-1 ${s.muted}`}>
              Shown in the browser tab, on the login screen and at the bottom of every page. Leave it empty
              to go back to the default.
            </p>
          </form>
          <div className={`divide-y ${s.divider}`}>
            <SettingSwitch
              label="Hide pages and covers"
              description="Shows a placeholder instead of every image, for everyone on this server."
              checked={config.hide_manga}
              onChange={() => toggle("hide_manga")}
            />
            <SettingSwitch
              label="Hide titles in grids"
              description="Lists show covers only, for everyone on this server."
              checked={config.hide_titles}
              onChange={() => toggle("hide_titles")}
            />
          </div>
        </div>
      )}

      {picking && <FolderPicker onPick={addPath} onClose={() => setPicking(false)} />}
      {moving && (
        <FolderPicker
          title="Where is this folder now?"
          onPick={moveTo}
          onClose={() => setMoving(null)}
        />
      )}
    </section>
  )
}
