import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import {
  BookOpen,
  BookCheck,
  Bookmark,
  Check,
  CircleCheck,
  Download,
  ExternalLink,
  Heart,
  LoaderCircle,
  PencilLine,
  RotateCcw,
  TriangleAlert,
} from "lucide-react"
import { toast } from "sonner"
import { ImageWithFallback } from "../components/ImageWithFallback"
import { StatusMessage } from "../components/StatusMessage"
import { useTheme } from "../context/ThemeContext"
import { useAuth } from "../context/AuthContext"
import { MangaManagePanel } from "../components/MangaManagePanel"
import { RatingPicker } from "../components/RatingPicker"
import { MetadataDialog } from "../components/MetadataDialog"
import { formatValue } from "../lib/metadata"
import { useDownloads } from "../context/DownloadsContext"
import * as offline from "../lib/offline"
import { useServerFeatures } from "../lib/features"
import { api, ApiError, imageUrl } from "../lib/api"

// A series' details and chapters. Without a connection, a downloaded series is shown from what's
// saved on the phone (offline.offlineManga): only downloaded chapters open, and the buttons that
// need the server are hidden.
export function MangaInfo() {
  const { mangaId } = useParams()
  const { theme } = useTheme()
  const { user: account, status } = useAuth()
  const isOffline = status === "offline"
  const dark = theme === "dark"
  const [manga, setManga] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const [showFullSummary, setShowFullSummary] = useState(false)
  const [downloadMenu, setDownloadMenu] = useState(false)
  const downloads = useDownloads()
  const features = useServerFeatures()

  const load = useCallback(() => {
    setError(null)
    const saved = offline.offlineManga(mangaId)
    if (isOffline && saved) {
      setManga(saved)
      return
    }
    const controller = new AbortController()
    api
      .manga(mangaId, controller.signal)
      .then((result) => {
        offline.refreshInfo(result)
        setManga(result)
      })
      .catch((error) => {
        if (error.name === "AbortError") return
        // The server didn't answer: a downloaded series still opens
        const fallback = error instanceof ApiError && error.status === 0 ? offline.offlineManga(mangaId) : null
        if (fallback) setManga(fallback)
        else setError(error)
      })
    return () => controller.abort()
  }, [mangaId, isOffline])

  useEffect(load, [load])

  const updateState = async (state) => {
    setSaving(true)
    try {
      const { user, rating } = await api.setState(mangaId, state)
      // Reset and read changes affect the resume point and chapter marks, so reload those
      if (state.reset || "is_read" in state) {
        setManga(await api.manga(mangaId))
      } else {
        setManga((previous) => ({ ...previous, user, rating }))
      }
    } catch (error) {
      toast.error(error.message)
    } finally {
      setSaving(false)
    }
  }

  const setChaptersRead = async (numbers, isRead) => {
    setSaving(true)
    try {
      const { user, read_chapters } = await api.setChaptersRead(mangaId, numbers, isRead)
      const read = new Set(read_chapters)
      setManga((previous) => ({
        ...previous,
        user,
        chapters: previous.chapters.map((chapter) => ({ ...chapter, is_read: read.has(chapter.number) })),
      }))
      return read
    } catch (error) {
      toast.error(error.message)
      return null
    } finally {
      setSaving(false)
    }
  }

  const toggleChapter = async (chapter) => {
    const read = await setChaptersRead([chapter.number], !chapter.is_read)
    if (!read || chapter.is_read) return
    // Offer to catch up the chapters before this one
    const earlier = manga.chapters
      .filter((other) => other.number < chapter.number && !read.has(other.number))
      .map((other) => other.number)
    if (earlier.length > 0) {
      toast(`Chapter ${chapter.number} marked read`, {
        action: {
          label: `Mark ${earlier.length} earlier read`,
          onClick: () => setChaptersRead(earlier, true),
        },
      })
    }
  }

  const startDownload = async (numbers) => {
    setDownloadMenu(false)
    if (!numbers.length) return
    toast.success(`Downloading ${numbers.length} ${numbers.length === 1 ? "chapter" : "chapters"}`)
    try {
      await offline.download(manga, numbers)
    } catch (error) {
      toast.error(error.message)
    }
  }

  const chapterDownload = async (chapter) => {
    const state = offline.chapterState(manga.id, chapter.number)
    if (state?.state === "done") {
      if (confirm(`Delete chapter ${chapter.number} from this ${offline.deviceName}?`)) offline.remove(manga.id, [chapter.number])
    } else if (state?.state === "failed") {
      offline.retry(manga.id, chapter.number)
    } else if (!state) {
      startDownload([chapter.number])
    }
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <StatusMessage message={error.message} onRetry={load} pose="sad" />
      </div>
    )
  }

  if (!manga) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-pulse">
        <div className={`w-48 aspect-[2/3] rounded-lg ${dark ? "bg-gray-800" : "bg-gray-200"}`} />
      </div>
    )
  }

  const { user, resume } = manga
  const local = Boolean(manga.offline)
  const onPhone = new Set(offline.downloadedChapters(manga.id))
  // Offline, only downloaded chapters open; the resume point counts only if it's one of them
  const readable = (number) => !local || onPhone.has(number)
  const atBeginning = resume.chapter === 1 && resume.page === 1
  const started = user.last_seen !== null && !user.is_read && !atBeginning && readable(resume.chapter)
  const firstOnPhone = [...onPhone][0]
  const readLink =
    !local || readable(resume.chapter)
      ? `/read/${manga.id}/${resume.chapter}/${resume.page}`
      : firstOnPhone !== undefined
        ? `/read/${manga.id}/${firstOnPhone}/1`
        : null
  const savedOnPhone = Boolean(downloads.manga[manga.id])
  const muted = dark ? "text-gray-400" : "text-gray-600"
  const toggleButton = (active) =>
    `inline-flex items-center gap-2 px-4 py-2 rounded-md border transition-colors disabled:opacity-60 ${
      active
        ? "border-brand-600 bg-brand-600/15 text-brand-500"
        : dark
          ? "border-gray-700 text-gray-300 hover:bg-gray-800"
          : "border-gray-300 text-gray-700 hover:bg-gray-100"
    }`

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col sm:flex-row gap-6 sm:gap-8 mb-10">
        <div className="w-40 sm:w-56 shrink-0 mx-auto sm:mx-0">
          <div className="aspect-[2/3] rounded-lg overflow-hidden bg-gray-200">
            <ImageWithFallback
              src={local ? (offline.coverUrl(manga.id) ?? "") : imageUrl(manga.cover_url)}
              alt={manga.title}
              className="w-full h-full object-cover"
            />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <h1 className={`mb-2 break-words ${dark ? "text-white" : "text-gray-900"}`}>
            {manga.title}
          </h1>
          <p className={`mb-4 ${muted}`}>
            {manga.release_year && `${manga.release_year} • `}
            {manga.total_chapters} {manga.total_chapters === 1 ? "chapter" : "chapters"}
            {manga.progress > 0 &&
              ` • ${manga.progress < 0.01 ? "<1" : Math.round(manga.progress * 100)}% read`}
          </p>
          {local && (
            <p className="mb-4 text-sm text-amber-500">
              Offline: {onPhone.size} {onPhone.size === 1 ? "chapter is" : "chapters are"} on this {offline.deviceName}.
            </p>
          )}

          {(features.seriesDetails || local) && (
          <SeriesDetails
            metadata={manga.metadata}
            dark={dark}
            muted={muted}
            showFull={showFullSummary}
            onToggleFull={() => setShowFullSummary((value) => !value)}
          />
          )}

          {features.ratings && !local && (
            <RatingPicker
              rating={manga.rating}
              disabled={saving}
              onChange={(value) => updateState({ rating: value })}
            />
          )}

          {manga.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-6">
              {manga.tags.map((tag) => {
                const className = `text-xs px-2 py-1 rounded ${
                  tag.nsfw
                    ? "bg-red-900/40 text-red-300"
                    : dark
                      ? "bg-gray-800 text-gray-300"
                      : "bg-gray-200 text-gray-700"
                }`
                // Search needs the server
                return local ? (
                  <span key={tag.tag} className={className}>
                    {tag.tag}
                  </span>
                ) : (
                  <Link
                    key={tag.tag}
                    to={`/search?q=${encodeURIComponent(`tag:${tag.tag.replaceAll(" ", "_")}`)}`}
                    className={className}
                  >
                    {tag.tag}
                  </Link>
                )
              })}
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            {readLink && (
            <Link
              to={readLink}
              className="inline-flex items-center gap-2 px-5 py-2 bg-brand-600 text-white rounded-md hover:bg-brand-700 transition-colors"
            >
              <BookOpen className="w-4 h-4" />
              {started ? `Continue chapter ${resume.chapter}, page ${resume.page}` : "Start reading"}
            </Link>
            )}
            {!local && (
            <>
            <button
              disabled={saving}
              onClick={() => updateState({ is_favorite: !user.is_favorite })}
              className={toggleButton(user.is_favorite)}
              aria-pressed={user.is_favorite}
            >
              <Heart className={`w-4 h-4 ${user.is_favorite ? "fill-current" : ""}`} />
              Favorite
            </button>
            <button
              disabled={saving}
              onClick={() => updateState({ is_queued: !user.is_queued })}
              className={toggleButton(user.is_queued)}
              aria-pressed={user.is_queued}
            >
              <Bookmark className={`w-4 h-4 ${user.is_queued ? "fill-current" : ""}`} />
              To read
            </button>
            <button
              disabled={saving}
              onClick={() => updateState({ is_read: !user.is_read })}
              className={toggleButton(user.is_read)}
              aria-pressed={user.is_read}
            >
              <BookCheck className="w-4 h-4" />
              {user.is_read ? "Read" : "Mark read"}
            </button>
            {offline.offlineNeedsHttps && (
              // Browsers only keep pages for offline reading on a secure address; say so instead of hiding it
              <button
                type="button"
                onClick={() => toast.info(offline.HTTPS_NOTICE, { duration: 8000 })}
                className={toggleButton(false)}
              >
                <Download className="w-4 h-4" />
                Download
              </button>
            )}
            {downloads.available && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setDownloadMenu((open) => !open)}
                  className={toggleButton(false)}
                  aria-expanded={downloadMenu}
                >
                  <Download className="w-4 h-4" />
                  Download
                </button>
                {downloadMenu && (
                  <div
                    className={`absolute z-20 mt-2 w-60 rounded-md border shadow-lg py-1 ${
                      dark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
                    }`}
                  >
                    {[
                      ["Unread chapters", manga.chapters.filter((chapter) => !chapter.is_read)],
                      ["All chapters", manga.chapters],
                    ].map(([label, list]) => {
                      const missing = list
                        .map((chapter) => chapter.number)
                        .filter((number) => !offline.chapterState(manga.id, number))
                      return (
                        <button
                          key={label}
                          type="button"
                          disabled={!missing.length}
                          onClick={() => startDownload(missing)}
                          className={`w-full text-left px-4 py-2 text-sm disabled:opacity-50 ${
                            dark ? "text-gray-200 hover:bg-gray-700" : "text-gray-800 hover:bg-gray-100"
                          }`}
                        >
                          {label} ({missing.length ? `${missing.length} to download` : `all on this ${offline.deviceName}`})
                        </button>
                      )
                    })}
                    {savedOnPhone && (
                      <button
                        type="button"
                        onClick={async () => {
                          setDownloadMenu(false)
                          if (!confirm(`Delete the downloaded chapters of "${manga.title}" from this ${offline.deviceName}?`)) return
                          await offline.remove(manga.id)
                          toast.success(`Deleted from this ${offline.deviceName}`)
                        }}
                        className={`w-full text-left px-4 py-2 text-sm text-red-500 ${
                          dark ? "hover:bg-gray-700" : "hover:bg-gray-100"
                        }`}
                      >
                        Delete from this {offline.deviceName}
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
            {features.seriesDetails && (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className={toggleButton(Boolean(manga.my_suggestion))}
              title={manga.my_suggestion ? "You have a suggestion waiting for review" : undefined}
            >
              <PencilLine className="w-4 h-4" />
              {account?.is_admin ? "Edit details" : manga.my_suggestion ? "Suggestion pending" : "Suggest edit"}
            </button>
            )}
            {(started || user.is_read) && (
              <button
                disabled={saving}
                onClick={() => updateState({ reset: true, is_read: false })}
                className={toggleButton(false)}
              >
                <RotateCcw className="w-4 h-4" />
                Start over
              </button>
            )}
            </>
            )}
          </div>
        </div>
      </div>

      {editing && (
        <MetadataDialog
          manga={manga}
          isAdmin={Boolean(account?.is_admin)}
          onClose={() => setEditing(false)}
          onSaved={load}
        />
      )}

      {account?.is_admin && !local && <MangaManagePanel manga={manga} onChanged={load} />}

      <div className="flex items-center justify-between gap-4 mb-4">
        <h2 className={dark ? "text-white" : "text-gray-900"}>Chapters</h2>
        {(features.chapterMarks || local) && manga.chapters.length > 1 && (
          <span className={`text-sm ${muted}`}>
            {manga.chapters.filter((chapter) => chapter.is_read).length} of {manga.chapters.length} read
          </span>
        )}
      </div>
      <ul
        className={`rounded-lg border divide-y ${
          dark ? "border-gray-800 divide-gray-800" : "border-gray-200 divide-gray-200"
        }`}
      >
        {manga.chapters.map((chapter) => {
          const current = started && chapter.number === resume.chapter
          const page = current ? resume.page : 1
          const canOpen = readable(chapter.number)
          const RowLink = canOpen ? Link : "div"
          return (
            <li
              key={chapter.number}
              className={`flex items-center transition-colors ${
                current
                  ? "bg-brand-600/15"
                  : !canOpen
                    ? "opacity-50"
                    : dark
                      ? "hover:bg-gray-900"
                      : "hover:bg-gray-100"
              }`}
            >
              <RowLink
                {...(canOpen ? { to: `/read/${manga.id}/${chapter.number}/${page}` } : { "aria-disabled": true })}
                className={`flex-1 min-w-0 flex items-center justify-between gap-4 pl-4 py-3 ${canOpen ? "" : "pr-4"}`}
              >
                <span
                  className={`min-w-0 truncate ${
                    chapter.is_read && !current ? muted : dark ? "text-gray-200" : "text-gray-800"
                  }`}
                >
                  <span className={muted}>{chapter.number}.</span> {chapter.title || `Chapter ${chapter.number}`}
                </span>
                <span className={`shrink-0 text-sm ${muted}`}>
                  {current
                    ? `Page ${page} of ${chapter.page_count}`
                    : !canOpen
                      ? `Not on ${offline.deviceName}`
                      : `${chapter.page_count} pages`}
                </span>
              </RowLink>
              {downloads.available && !local && (
                <ChapterDownload
                  state={offline.chapterState(manga.id, chapter.number)}
                  muted={muted}
                  onClick={() => chapterDownload(chapter)}
                />
              )}
              {local && onPhone.has(chapter.number) && (
                <span className="shrink-0 px-4 py-3" title={`On this ${offline.deviceName}`}>
                  <CircleCheck className="w-5 h-5 text-brand-500" />
                </span>
              )}
              {features.chapterMarks && !local && (
              <button
                type="button"
                disabled={saving}
                onClick={() => toggleChapter(chapter)}
                aria-pressed={chapter.is_read}
                aria-label={chapter.is_read ? `Mark chapter ${chapter.number} unread` : `Mark chapter ${chapter.number} read`}
                title={chapter.is_read ? "Read. Tap to mark unread" : "Mark read"}
                className="shrink-0 px-4 py-3 disabled:opacity-60"
              >
                <span
                  className={`flex items-center justify-center w-6 h-6 rounded-full border transition-colors ${
                    chapter.is_read
                      ? "bg-brand-600 border-brand-600 text-white"
                      : dark
                        ? "border-gray-600 text-transparent hover:border-gray-400"
                        : "border-gray-400 text-transparent hover:border-gray-600"
                  }`}
                >
                  <Check className="w-4 h-4" />
                </span>
              </button>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// Summary and credits from ComicInfo.xml or approved edits. Missing details are left out.
function SeriesDetails({ metadata, dark, muted, showFull, onToggleFull }) {
  if (!metadata) return null
  const credits = [
    ["Writer", metadata.writer],
    ["Artist", metadata.artist !== metadata.writer ? metadata.artist : null],
    ["Publisher", metadata.publisher],
    ["Language", metadata.language],
    ["Age rating", metadata.age_rating],
    ["Format", metadata.format],
    ["Direction", metadata.reading_direction && formatValue("reading_direction", metadata.reading_direction)],
  ].filter(([, value]) => value)
  const long = (metadata.summary ?? "").length > 300

  return (
    <div className="mb-6 space-y-3">
      {metadata.summary && (
        <div>
          <p
            className={`whitespace-pre-line break-words ${dark ? "text-gray-300" : "text-gray-700"} ${
              long && !showFull ? "line-clamp-4" : ""
            }`}
          >
            {metadata.summary}
          </p>
          {long && (
            <button type="button" onClick={onToggleFull} className="text-sm text-brand-500 hover:text-brand-400">
              {showFull ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}
      {metadata.genres?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {metadata.genres.map((genre) => (
            <span key={genre} className="text-xs px-2 py-1 rounded-full border border-brand-600/40 text-brand-500">
              {genre}
            </span>
          ))}
        </div>
      )}
      {(credits.length > 0 || metadata.web) && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {credits.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className={muted}>{label}</dt>
              <dd className={`min-w-0 break-words ${dark ? "text-gray-200" : "text-gray-800"}`}>{value}</dd>
            </div>
          ))}
          {metadata.web && (
            <div className="contents">
              <dt className={muted}>Link</dt>
              <dd className="min-w-0">
                <a
                  href={metadata.web}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-brand-500 hover:text-brand-400 break-all"
                >
                  {metadata.web.replace(/^https?:\/\//, "")}
                  <ExternalLink className="w-3 h-3 shrink-0" />
                </a>
              </dd>
            </div>
          )}
        </dl>
      )}
    </div>
  )
}

// Download state of one chapter: tap to download, retry, or delete it from the phone
function ChapterDownload({ state, muted, onClick }) {
  const status = state?.state
  const percent = state?.total ? Math.round((state.done / state.total) * 100) : 0
  const label =
    status === "done"
      ? `Downloaded. Tap to delete from this ${offline.deviceName}`
      : status === "failed"
        ? `Download failed: ${state.error ?? ""}. Tap to try again`
        : status
          ? `Downloading ${percent}%`
          : "Download for offline reading"
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={status === "queued" || status === "downloading"}
      aria-label={label}
      title={label}
      className={`shrink-0 pl-2 py-3 flex items-center gap-1 text-xs tabular-nums ${muted}`}
    >
      {status === "done" ? (
        <CircleCheck className="w-5 h-5 text-brand-500" />
      ) : status === "failed" ? (
        <TriangleAlert className="w-5 h-5 text-red-500" />
      ) : status ? (
        <>
          <LoaderCircle className="w-5 h-5 animate-spin" />
          {status === "downloading" && `${percent}%`}
        </>
      ) : (
        <Download className="w-5 h-5" />
      )}
    </button>
  )
}
