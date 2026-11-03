import { Download, ExternalLink, ShieldCheck } from "lucide-react"
import { useStyles } from "../hooks/useStyles"

const formatSize = (bytes) => (bytes ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : "")

// Shows a new release: version, notes, then download progress and Android's install step
export function UpdateDialog({ update, status, progress, error, onUpdate, onAllowInstalls, onLater, onSkip }) {
  const s = useStyles()
  const busy = status === "downloading" || status === "installing"
  const percent = progress === null || progress === undefined ? null : Math.round(progress * 100)

  return (
    <div className="fixed inset-0 z-[70] bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="update-title"
        className={`w-full sm:max-w-md max-h-[85vh] flex flex-col rounded-t-lg sm:rounded-lg border pb-[env(safe-area-inset-bottom)] ${
          s.dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
        }`}
      >
        <div className="p-5 pb-3">
          <h2 id="update-title" className={`flex items-center gap-2 ${s.dark ? "text-white" : "text-gray-900"}`}>
            <Download className="w-5 h-5 text-blue-500" /> Update available
          </h2>
          <p className={`text-sm mt-1 ${s.muted}`}>
            Version {update.version} {update.installed && `(you have ${update.installed})`}
            {update.size ? ` • ${formatSize(update.size)}` : ""}
          </p>
        </div>

        {update.notes && (
          <div className={`mx-5 mb-3 p-3 rounded-md overflow-y-auto text-sm whitespace-pre-wrap ${s.dark ? "bg-gray-800 text-gray-300" : "bg-gray-100 text-gray-700"}`}>
            {update.notes}
          </div>
        )}

        <div className="px-5 pb-5 space-y-3">
          {status === "downloading" && (
            <div>
              <div className={`h-2 rounded-full overflow-hidden ${s.dark ? "bg-gray-800" : "bg-gray-200"}`}>
                <div
                  className={`h-full bg-blue-600 transition-[width] ${percent === null ? "w-1/3 animate-pulse" : ""}`}
                  style={percent === null ? undefined : { width: `${percent}%` }}
                />
              </div>
              <p className={`text-xs mt-1 ${s.muted}`}>Downloading{percent !== null && ` ${percent}%`}…</p>
            </div>
          )}

          {status === "needs-permission" && (
            <div className={`text-sm p-3 rounded-md ${s.dark ? "bg-blue-950/50 text-blue-200" : "bg-blue-50 text-blue-900"}`}>
              Android needs your permission for myMangaLib to install updates. Turn on{" "}
              <strong>Allow from this source</strong>, then come back. The update installs straight away.
            </div>
          )}

          {status === "error" && error && (
            <p className="text-sm text-red-500">
              {error.message}{" "}
              {update.page && (
                <a href={update.page} target="_blank" rel="noopener noreferrer" className="underline inline-flex items-center gap-1">
                  Download from GitHub <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </p>
          )}

          <p className={`text-xs flex items-center gap-1.5 ${s.muted}`}>
            <ShieldCheck className="w-3.5 h-3.5" />
            Checked against GitHub's checksum and the app's signature before installing.
          </p>

          <div className="flex flex-wrap gap-2 pt-1">
            {status === "needs-permission" ? (
              <button className={s.primaryButton} onClick={onAllowInstalls}>
                Open settings
              </button>
            ) : (
              <button className={s.primaryButton} onClick={onUpdate} disabled={busy}>
                {status === "downloading"
                  ? "Downloading…"
                  : status === "installing"
                    ? "Opening installer…"
                    : status === "error"
                      ? "Try again"
                      : "Update"}
              </button>
            )}
            <button className={s.button} onClick={onLater} disabled={busy}>
              Later
            </button>
            <button className={`${s.button} ml-auto`} onClick={onSkip} disabled={busy}>
              Skip this version
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
