import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import { BookOpen, BookCheck, Bookmark, Heart, RotateCcw } from "lucide-react"
import { toast } from "sonner"
import { ImageWithFallback } from "../components/figma/ImageWithFallback"
import { StatusMessage } from "../components/StatusMessage"
import { useTheme } from "../context/ThemeContext"
import { api, imageUrl } from "../lib/api"

export function MangaInfo() {
  const { mangaId } = useParams()
  const { theme } = useTheme()
  const dark = theme === "dark"
  const [manga, setManga] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    const controller = new AbortController()
    setError(null)
    api
      .manga(mangaId, controller.signal)
      .then(setManga)
      .catch((error) => error.name !== "AbortError" && setError(error))
    return () => controller.abort()
  }, [mangaId])

  useEffect(load, [load])

  const updateState = async (state) => {
    setSaving(true)
    try {
      const { user } = await api.setState(mangaId, state)
      // Reset changes the resume point, so reload to keep everything in sync
      if (state.reset) {
        setManga(await api.manga(mangaId))
      } else {
        setManga((previous) => ({ ...previous, user }))
      }
    } catch (error) {
      toast.error(error.message)
    } finally {
      setSaving(false)
    }
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <StatusMessage message={error.message} onRetry={load} />
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
  const atBeginning = resume.chapter === 1 && resume.page === 1
  const started = user.last_seen !== null && !user.is_read && !atBeginning
  const readLink = `/read/${manga.id}/${resume.chapter}/${resume.page}`
  const muted = dark ? "text-gray-400" : "text-gray-600"
  const toggleButton = (active) =>
    `inline-flex items-center gap-2 px-4 py-2 rounded-md border transition-colors disabled:opacity-60 ${
      active
        ? "border-blue-600 bg-blue-600/15 text-blue-500"
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
              src={imageUrl(manga.cover_url)}
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

          {manga.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-6">
              {manga.tags.map((tag) => (
                <Link
                  key={tag.tag}
                  to={`/search?q=${encodeURIComponent(`tag:${tag.tag.replaceAll(" ", "_")}`)}`}
                  className={`text-xs px-2 py-1 rounded ${
                    tag.nsfw
                      ? "bg-red-900/40 text-red-300"
                      : dark
                        ? "bg-gray-800 text-gray-300"
                        : "bg-gray-200 text-gray-700"
                  }`}
                >
                  {tag.tag}
                </Link>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <Link
              to={readLink}
              className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <BookOpen className="w-4 h-4" />
              {started ? `Continue chapter ${resume.chapter}, page ${resume.page}` : "Start reading"}
            </Link>
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
          </div>
        </div>
      </div>

      <h2 className={`mb-4 ${dark ? "text-white" : "text-gray-900"}`}>Chapters</h2>
      <ul
        className={`rounded-lg border divide-y ${
          dark ? "border-gray-800 divide-gray-800" : "border-gray-200 divide-gray-200"
        }`}
      >
        {manga.chapters.map((chapter) => {
          const current = started && chapter.number === resume.chapter
          const page = current ? resume.page : 1
          return (
            <li key={chapter.number}>
              <Link
                to={`/read/${manga.id}/${chapter.number}/${page}`}
                className={`flex items-center justify-between gap-4 px-4 py-3 transition-colors ${
                  current
                    ? "bg-blue-600/15"
                    : dark
                      ? "hover:bg-gray-900"
                      : "hover:bg-gray-100"
                }`}
              >
                <span className={`min-w-0 truncate ${dark ? "text-gray-200" : "text-gray-800"}`}>
                  <span className={muted}>{chapter.number}.</span> {chapter.title || `Chapter ${chapter.number}`}
                </span>
                <span className={`shrink-0 text-sm ${muted}`}>
                  {current ? `Page ${page} of ${chapter.page_count}` : `${chapter.page_count} pages`}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
