import { useEffect, useState } from "react"
import { Download } from "lucide-react"
import { useDownloads } from "../context/DownloadsContext"
import { useStyles } from "../hooks/useStyles"
import { Tenma } from "../components/Tenma"
import { MangaCard } from "../components/MangaCard"
import * as offline from "../lib/offline"

export const formatBytes = (bytes) =>
  bytes >= 1024 ** 3
    ? `${(bytes / 1024 ** 3).toFixed(1)} GB`
    : bytes >= 1024 ** 2
      ? `${Math.round(bytes / 1024 ** 2)} MB`
      : `${Math.round(bytes / 1024)} KB`

// The line over a cover: what's still downloading, what failed, or how much is on the phone
function downloadBadge(item) {
  const entries = Object.values(item.chapters)
  const done = entries.filter((entry) => entry.state === "done").length
  const busy = entries.filter((entry) => entry.state === "queued" || entry.state === "downloading")
  const failed = entries.filter((entry) => entry.state === "failed").length
  if (busy.length) {
    const pages = busy.reduce((sum, entry) => sum + (entry.total || 0), 0)
    const fetched = busy.reduce((sum, entry) => sum + (entry.done || 0), 0)
    return pages ? `Downloading ${Math.round((fetched / pages) * 100)}%` : "Waiting…"
  }
  if (failed) return `${failed} failed`
  const total = item.info?.chapters?.length
  const where = `on ${offline.deviceName}`
  return total ? `${done} of ${total} ${where}` : `${done} ${where}`
}

// Series saved on this phone for offline reading, as a grid of covers. Tapping one opens the
// series page, which also works without a connection.
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
        <p className={s.muted}>
          {offline.offlineNeedsHttps ? offline.HTTPS_NOTICE : "Downloads are available in the Android app."}
        </p>
      </div>
    )
  }

  const series = Object.entries(manga)
    .map(([id, item]) => ({ id, item, card: offline.offlineManga(id) }))
    .sort((a, b) => a.card.title.localeCompare(b.card.title))

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-baseline justify-between gap-4 mb-6">
        <h2 className={s.dark ? "text-white" : "text-gray-900"}>
          Downloads
          {series.length > 0 && <span className="ml-2 text-sm font-normal text-gray-500">{series.length}</span>}
        </h2>
        {bytes !== null && <span className={`text-sm ${s.muted}`}>{formatBytes(bytes)} used</span>}
      </div>

      {!ready ? (
        <p className={s.muted}>Loading…</p>
      ) : series.length === 0 ? (
        <div className={`${s.card} text-center`}>
          <Tenma pose="download" size="h-52 sm:h-64" className="mx-auto mb-4" />
          <p className={s.text}>Nothing downloaded yet.</p>
          <p className={`text-sm mt-1 ${s.muted}`}>
            Open a series and use <Download className="inline w-4 h-4" /> Download to read it without a connection.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-6">
          {series.map(({ id, item, card }) => (
            <MangaCard
              key={id}
              manga={card}
              coverSrc={offline.coverUrl(id) ?? ""}
              badge={downloadBadge(item)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
