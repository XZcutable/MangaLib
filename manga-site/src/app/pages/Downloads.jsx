import { useEffect, useState } from "react"
import { Link } from "react-router"
import { BookOpen, Download, RotateCw, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useDownloads } from "../context/DownloadsContext"
import { useStyles } from "../hooks/useStyles"
import * as offline from "../lib/offline"

export const formatBytes = (bytes) =>
  bytes >= 1024 ** 3
    ? `${(bytes / 1024 ** 3).toFixed(1)} GB`
    : bytes >= 1024 ** 2
      ? `${Math.round(bytes / 1024 ** 2)} MB`
      : `${Math.round(bytes / 1024)} KB`

const sortedChapters = (manga) =>
  Object.entries(manga.chapters)
    .map(([number, entry]) => ({ number: Number(number), ...entry }))
    .sort((a, b) => a.number - b.number)

// Chapters saved on this phone for offline reading. Works without a connection.
export function Downloads() {
  const s = useStyles()
  const { available, ready, manga, version } = useDownloads()
  const [bytes, setBytes] = useState(null)

  useEffect(() => {
    if (available) offline.usage().then(setBytes)
  }, [available, version])

  if (!available) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <p className={s.muted}>Downloads are available in the Android app.</p>
      </div>
    )
  }

  const series = Object.entries(manga).sort(([, a], [, b]) => a.title.localeCompare(b.title))

  const removeSeries = async (id, title) => {
    if (!confirm(`Delete the downloaded chapters of "${title}" from this phone?`)) return
    await offline.remove(id)
    toast.success("Deleted")
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-baseline justify-between gap-4 mb-6">
        <h1 className={s.dark ? "text-white" : "text-gray-900"}>Downloads</h1>
        {bytes !== null && <span className={`text-sm ${s.muted}`}>{formatBytes(bytes)} used</span>}
      </div>

      {!ready ? (
        <p className={s.muted}>Loading…</p>
      ) : series.length === 0 ? (
        <div className={s.card}>
          <p className={s.text}>Nothing downloaded yet.</p>
          <p className={`text-sm mt-1 ${s.muted}`}>
            Open a series and use <Download className="inline w-4 h-4" /> Download to read it without a connection.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {series.map(([id, item]) => {
            const chapters = sortedChapters(item)
            const cover = offline.coverUrl(id)
            return (
              <section key={id} className={s.card}>
                <div className="flex gap-4 mb-4">
                  {cover && <img src={cover} alt="" className="w-16 aspect-[2/3] object-cover rounded shrink-0" />}
                  <div className="min-w-0 flex-1">
                    <h2 className={`${s.dark ? "text-white" : "text-gray-900"} break-words`}>{item.title}</h2>
                    <p className={`text-sm ${s.muted}`}>
                      {chapters.filter((chapter) => chapter.state === "done").length} of {chapters.length} chapters ready
                    </p>
                  </div>
                  <button
                    className="self-start p-2 text-red-500 hover:text-red-400"
                    onClick={() => removeSeries(id, item.title)}
                    aria-label={`Delete downloads of ${item.title}`}
                    title="Delete from this phone"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
                <ul className={`divide-y ${s.divider}`}>
                  {chapters.map((chapter) => (
                    <li key={chapter.number} className="flex items-center gap-3 py-2">
                      <span className={`flex-1 min-w-0 truncate ${s.text}`}>
                        {chapter.chapter?.title || `Chapter ${chapter.number}`}
                      </span>
                      <DownloadStatus mangaId={id} chapter={chapter} />
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}

function DownloadStatus({ mangaId, chapter }) {
  const s = useStyles()
  if (chapter.state === "done") {
    return (
      <>
        <Link
          to={`/read/${mangaId}/${chapter.number}/1`}
          className="inline-flex items-center gap-1 text-sm text-brand-500 hover:text-brand-400"
        >
          <BookOpen className="w-4 h-4" /> Read
        </Link>
        <button
          className={`p-1 ${s.muted} hover:text-red-500`}
          onClick={() => offline.remove(mangaId, [chapter.number])}
          aria-label={`Delete chapter ${chapter.number} from this phone`}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </>
    )
  }
  if (chapter.state === "failed") {
    return (
      <>
        <span className="text-xs text-red-500 truncate max-w-[40%]" title={chapter.error}>
          {chapter.error || "Failed"}
        </span>
        <button
          className={`p-1 ${s.muted}`}
          onClick={() => offline.retry(Number(mangaId), chapter.number)}
          aria-label="Try again"
        >
          <RotateCw className="w-4 h-4" />
        </button>
      </>
    )
  }
  const percent = chapter.total ? Math.round((chapter.done / chapter.total) * 100) : 0
  return (
    <span className={`text-xs tabular-nums ${s.muted}`}>
      {chapter.state === "queued" ? "Waiting…" : `${percent}%`}
    </span>
  )
}
