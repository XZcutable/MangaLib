import { useEffect, useState } from "react"
import { Package, X } from "lucide-react"
import { toast } from "sonner"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"
import { waitForJob } from "../../lib/metadata"

const formatBytes =(bytes) => {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(0)} MB`
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`

// Owner only: packs every series' image folders into .cbz files. Checks first, asks, then runs as one job.
// `runningJob` is a crunch already running when Settings opened (from GET /library).
export function CrunchAll({ runningJob, onFinished = () => {} }) {
  const s = useStyles()
  const [checking, setChecking] = useState(false)
  const [preview, setPreview] = useState(null)
  const [job, setJob] = useState(null)
  const [failures, setFailures] = useState([])

  useEffect(() => {
    if (runningJob && !job) follow(runningJob)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runningJob?.id])

  const check = async () => {
    setChecking(true)
    try {
      const result = await api.crunchPreview()
      if (result.job) follow(result.job)
      else setPreview(result)
    } catch (error) {
      toast.error(error.message)
    } finally {
      setChecking(false)
    }
  }

  const follow = async (started) => {
    setJob(started)
    setFailures([])
    try {
      const done = await waitForJob(started, setJob)
      setFailures(done.failures ?? [])
      if (done.failures?.length || done.leftover_files) toast.warning(done.message, { duration: 10000 })
      else toast.success(done.message ?? "Done")
    } catch (error) {
      toast.error(error.message)
    } finally {
      setJob(null)
      onFinished()
    }
  }

  const start = async () => {
    const ids = preview.series.map((series) => series.id)
    setPreview(null)
    try {
      follow((await api.crunchAll(ids)).job)
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <div className="mt-6">
      <h3 className={s.subheading}>Crunch all series</h3>
      <p className={`text-sm mb-3 ${s.muted}`}>
        Packs every folder of page images in the library into a .cbz file, one series at a time. You'll see
        what would change before anything happens. People can keep reading while it runs, and you can leave
        this page: it carries on in the background.
      </p>

      {job ? (
        <div aria-live="polite">
          <div className={`flex justify-between gap-3 text-sm mb-1 ${s.text}`}>
            <span className="truncate">{job.current ? `Crunching ${job.current}` : "Starting…"}</span>
            <span className="shrink-0">
              {job.done} / {job.total} chapters
            </span>
          </div>
          <div className={`h-2 rounded-full overflow-hidden ${s.dark ? "bg-gray-800" : "bg-gray-200"}`}>
            <div
              className="h-full bg-brand-600 transition-all"
              style={{ width: `${job.total ? (100 * job.done) / job.total : 0}%` }}
            />
          </div>
        </div>
      ) : (
        <button className={s.button} onClick={check} disabled={checking}>
          <span className="inline-flex items-center gap-2">
            <Package className="w-4 h-4" /> {checking ? "Checking the library…" : "Crunch all series…"}
          </span>
        </button>
      )}

      {failures.length > 0 && (
        <div className="mt-3 text-sm">
          <p className="text-red-500 mb-1">Left as they were:</p>
          <ul className={`list-disc pl-5 space-y-1 ${s.muted}`}>
            {failures.map((failure, index) => (
              <li key={index}>
                <span className={s.text}>{failure.title}</span>: {failure.error}
              </li>
            ))}
          </ul>
        </div>
      )}

      {preview && <PreviewDialog preview={preview} onConfirm={start} onClose={() => setPreview(null)} />}
    </div>
  )
}

function PreviewDialog({ preview, onConfirm, onClose }) {
  const s = useStyles()
  const { series, skipped, disk } = preview
  const nothing = series.length === 0

  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[60] bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Crunch all series"
        onClick={(event) => event.stopPropagation()}
        className={`w-full sm:max-w-lg max-h-[85vh] flex flex-col rounded-t-lg sm:rounded-lg border ${
          s.dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
        }`}
      >
        <div className="flex items-center justify-between p-4 pb-2">
          <h2 className={s.dark ? "text-white" : "text-gray-900"}>Crunch all series</h2>
          <button onClick={onClose} className={`p-1 ${s.muted}`} aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className={`px-4 pb-3 text-sm space-y-2 ${s.text}`}>
          {nothing ? (
            <p>Nothing to crunch: every series is already in .cbz, .zip or .pdf files.</p>
          ) : (
            <>
              <p>
                Pack {plural(preview.total_chapters, "chapter")} in {series.length} series{" "}
                ({formatBytes(preview.total_bytes)}) into .cbz files. Each folder's images are deleted once its
                .cbz is in use. Other files in the folders are kept.
              </p>
              <p className={s.muted}>
                Reading keeps working. Progress, scores and read marks carry over.
              </p>
              {disk.free !== null && (
                <p className={disk.enough ? s.muted : "text-red-500"}>
                  {disk.enough
                    ? `Needs up to ${formatBytes(disk.needed)} of free space while working; ${formatBytes(disk.free)} free.`
                    : `Not enough free space: the largest series needs ${formatBytes(disk.needed)} while it's packed, but only ${formatBytes(disk.free)} is free.`}
                </p>
              )}
            </>
          )}
        </div>

        <ul className={`flex-1 overflow-y-auto border-y divide-y ${s.divider}`}>
          {series.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
              <span className={`truncate ${s.text}`}>{item.title}</span>
              <span className={`shrink-0 ${s.muted}`}>
                {plural(item.chapters, "chapter")} · {formatBytes(item.bytes)}
              </span>
            </li>
          ))}
          {skipped.map((item) => (
            <li key={`skipped-${item.id}`} className="px-4 py-2 text-sm">
              <span className={s.muted}>Skipped: </span>
              <span className={s.text}>{item.title}</span>
              <span className="block text-red-500">{item.reason}</span>
            </li>
          ))}
        </ul>

        <div className="flex justify-end gap-2 p-4">
          <button className={s.button} onClick={onClose}>
            {nothing ? "Close" : "Cancel"}
          </button>
          {!nothing && (
            <button className={s.primaryButton} onClick={onConfirm} disabled={!disk.enough}>
              Crunch {series.length} series
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
