import { useCallback, useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { useStyles } from "../../hooks/useStyles"
import { api, parseServerDate } from "../../lib/api"
import { reportRestarting } from "../../lib/serverStatus"
import { useAuth } from "../../context/AuthContext"
import { SettingSwitch } from "./SettingSwitch"

const BUSY = ["checking", "downloading", "applying"]

const formatSize = (bytes) => (bytes ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : "")
const formatDate = (value) => (value ? parseServerDate(value).toLocaleString() : "never")

// Owner only: new server versions download in the background and are installed when the owner applies them
export function ServerUpdatesSection() {
  const s = useStyles()
  const { refreshUser } = useAuth()
  const [update, setUpdate] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [working, setWorking] = useState(false)

  const load = useCallback(
    () =>
      api
        .serverUpdate()
        .then(({ update }) => setUpdate(update))
        .catch((error) => toast.error(error.message)),
    [],
  )
  useEffect(() => {
    load()
  }, [load])

  // Follows a check or download while it runs
  const busy = BUSY.includes(update?.status)
  useEffect(() => {
    if (!busy || update?.status === "applying") return
    const timer = setInterval(load, 1000)
    return () => clearInterval(timer)
  }, [busy, update?.status, load])

  const run = async (action, after) => {
    setWorking(true)
    try {
      const { update } = await action()
      setUpdate(update)
      after?.(update)
      refreshUser()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setWorking(false)
    }
  }

  const apply = () =>
    run(api.applyServerUpdate, () => {
      setConfirming(false)
      reportRestarting("updating")
    })

  const setAutoUpdate = async (value) => {
    try {
      const config = await api.updateServerConfig({ auto_update: value })
      setUpdate((current) => current && { ...current, auto_update: config.auto_update })
    } catch (error) {
      toast.error(error.message)
    }
  }

  if (!update) {
    return (
      <section className={s.card}>
        <h2 className={s.heading}>Server updates</h2>
        <p className={s.muted}>Loading…</p>
      </section>
    )
  }

  const { status, latest, progress } = update
  const percent = progress?.total ? Math.round((progress.done / progress.total) * 100) : null
  const version = update.staged_version || latest?.version
  const code = "rounded bg-gray-500/15 px-1"

  return (
    <section className={s.card}>
      <h2 className={s.heading}>Server updates</h2>
      <p className={`text-sm mb-1 ${s.muted}`}>
        Running version <span className={s.text}>{update.current_version}</span>
        {update.updated_from && ` (updated from ${update.updated_from})`}
        {" · "}Last checked {formatDate(update.last_check)}
      </p>

      {status === "idle" && <p className={`text-sm mt-3 ${s.text}`}>The server is up to date.</p>}
      {status === "checking" && <p className={`text-sm mt-3 ${s.text}`}>Checking for updates…</p>}

      {latest && status !== "idle" && status !== "checking" && (
        <div className={`mt-3 rounded-md border p-4 ${s.divider}`}>
          <p className={s.text}>
            {status === "ready"
              ? `Version ${version} is downloaded and ready to install.`
              : status === "applying"
                ? `Installing version ${version}…`
                : `Version ${latest.version} is available.`}
            {latest.size ? <span className={`text-sm ${s.muted}`}> {formatSize(latest.size)}</span> : null}
          </p>
          {latest.notes && (
            <details className="mt-2">
              <summary className={`cursor-pointer text-sm ${s.muted}`}>What's new</summary>
              <p className={`mt-2 whitespace-pre-wrap text-sm ${s.text}`}>{latest.notes}</p>
            </details>
          )}

          {status === "downloading" && (
            <div className="mt-3">
              <div className={`h-2 overflow-hidden rounded-full ${s.dark ? "bg-gray-800" : "bg-gray-200"}`}>
                <div className="h-full bg-brand-600 transition-all" style={{ width: `${percent ?? 5}%` }} />
              </div>
              <p className={`mt-1 text-xs ${s.muted}`}>
                {progress?.phase === "unpacking" ? (
                  "Unpacking…"
                ) : (
                  <>
                    Downloading{percent !== null && ` ${percent}%`} ({formatSize(progress?.done) || "0 MB"} of{" "}
                    {formatSize(progress?.total) || "?"})
                  </>
                )}
              </p>
            </div>
          )}

          {status === "needs_image" && (
            <p className={`mt-3 text-sm ${s.text}`}>
              This version can't be installed from here. On the server, run{" "}
              <code className={code}>docker compose pull</code> and then <code className={code}>docker compose up -d</code>.
            </p>
          )}

          {status === "ready" && !update.can_apply && (
            <p className={`mt-3 text-sm ${s.muted}`}>{update.apply_problem}</p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            {status === "ready" && update.can_apply && !confirming && (
              <button className={s.primaryButton} onClick={() => setConfirming(true)} disabled={working}>
                Apply and restart
              </button>
            )}
            {(status === "available" || status === "failed") && latest.has_bundle && (
              <button className={s.primaryButton} onClick={() => run(api.downloadServerUpdate)} disabled={working}>
                {status === "failed" ? "Try again" : "Download"}
              </button>
            )}
            {(status === "ready" || status === "downloading" || status === "failed") && !confirming && (
              <button className={s.button} onClick={() => run(api.discardServerUpdate)} disabled={working}>
                {status === "downloading" ? "Cancel" : "Discard"}
              </button>
            )}
            {latest.url && (
              <a
                href={latest.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-brand-500 hover:text-brand-400"
              >
                Release page
              </a>
            )}
          </div>

          {confirming && (
            <div className="mt-4 rounded-md border border-brand-600/50 bg-brand-600/10 p-4">
              <p className={`text-sm ${s.text}`}>
                The server restarts to install {version}. Anyone using it sees an "updating" screen for about a
                minute and then returns to their page. The database is backed up first, and if the new version
                doesn't start, the server goes back to {update.current_version} by itself.
              </p>
              <div className="mt-3 flex flex-wrap gap-3">
                <button className={s.primaryButton} onClick={apply} disabled={working}>
                  {working ? "Applying…" : `Install ${version} now`}
                </button>
                <button className={s.button} onClick={() => setConfirming(false)} disabled={working}>
                  Not now
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {update.error && status !== "needs_image" && <p className="mt-3 text-sm text-red-500">{update.error}</p>}

      <div className={`mt-4 divide-y ${s.divider}`}>
        <SettingSwitch
          label="Update automatically"
          description="Checks GitHub Releases every few hours and downloads new versions in the background. Nothing is installed until you apply it."
          checked={update.auto_update}
          onChange={setAutoUpdate}
          disabled={update.auto_update_locked}
          disabledReason="Turned off when the server was started (--no-auto-update or AUTO_UPDATE=false). You can still check by hand."
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button className={s.button} onClick={() => run(api.checkServerUpdate)} disabled={working || busy}>
          <span className="inline-flex items-center gap-2">
            <RefreshCw className={`h-4 w-4 ${status === "checking" ? "animate-spin" : ""}`} />
            {status === "checking" ? "Checking…" : "Check now"}
          </span>
        </button>
      </div>
    </section>
  )
}
