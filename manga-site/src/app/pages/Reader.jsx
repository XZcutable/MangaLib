import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { ArrowLeft, ChevronLeft, ChevronRight, Maximize2, MoveHorizontal } from "lucide-react"
import { api, imageUrl } from "../lib/api"
import { getLocal, setLocal } from "../lib/storage"
import { keepScreenOn } from "../lib/native"

const PRELOAD_AHEAD = 3
const SAVE_DELAY_MS = 600
const SWIPE_DISTANCE = 50

// Full-screen page reader. URL: /read/:mangaId/:chapter/:page
// Page turns replace the history entry, so Back leaves the reader instead of stepping through pages.
export function Reader() {
  const params = useParams()
  const mangaId = Number(params.mangaId)
  const chapterNumber = Number(params.chapter)
  const pageNumber = Number(params.page)
  const navigate = useNavigate()

  const [chapter, setChapter] = useState(null)
  const [error, setError] = useState(null)
  const [showControls, setShowControls] = useState(false)
  const [rightToLeft, setRightToLeft] = useState(() => getLocal("readerDirection", "ltr") === "rtl")
  const [fitWidth, setFitWidth] = useState(() => getLocal("readerFit", "screen") === "width")
  const touchStart = useRef(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    keepScreenOn(true)
    return () => keepScreenOn(false)
  }, [])
  useEffect(() => setLocal("readerDirection", rightToLeft ? "rtl" : "ltr"), [rightToLeft])
  useEffect(() => setLocal("readerFit", fitWidth ? "width" : "screen"), [fitWidth])

  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    api
      .chapter(mangaId, chapterNumber, controller.signal)
      .then(setChapter)
      .catch((error) => error.name !== "AbortError" && setError(error))
    return () => controller.abort()
  }, [mangaId, chapterNumber])

  const loaded = chapter && chapter.manga_id === mangaId && chapter.number === chapterNumber
  const page = loaded ? chapter.pages.find((p) => p.number === pageNumber) : null

  // The page being shown or just requested. Taps read this instead of the URL params, because
  // the params update a render later and a quick second tap would otherwise repeat the first.
  const position = useRef({ chapter: chapterNumber, page: pageNumber })
  useEffect(() => {
    position.current = { chapter: chapterNumber, page: pageNumber }
  }, [chapterNumber, pageNumber])

  const goTo = useCallback(
    (chapterTo, pageTo) => {
      position.current = { chapter: chapterTo, page: pageTo }
      navigate(`/read/${mangaId}/${chapterTo}/${pageTo}`, { replace: true })
    },
    [navigate, mangaId],
  )

  // Opening a page past the end (e.g. from a stale link) goes to the last page instead
  useEffect(() => {
    if (loaded && !page && chapter.page_count > 0) {
      goTo(chapterNumber, Math.min(Math.max(1, pageNumber), chapter.page_count))
    }
  }, [loaded, page, chapter, chapterNumber, pageNumber, goTo])

  const next = useCallback(() => {
    const { chapter: at, page: atPage } = position.current
    // Ignore taps while the next chapter is still loading
    if (!chapter || chapter.manga_id !== mangaId || chapter.number !== at) return
    if (atPage < chapter.page_count) goTo(at, atPage + 1)
    else if (chapter.next_chapter !== null) goTo(chapter.next_chapter, 1)
    else navigate(`/manga/${mangaId}`, { replace: true })
  }, [chapter, goTo, navigate, mangaId])

  const previous = useCallback(async () => {
    const { chapter: at, page: atPage } = position.current
    if (!chapter || chapter.manga_id !== mangaId || chapter.number !== at) return
    if (atPage > 1) goTo(at, atPage - 1)
    else if (chapter.previous_chapter !== null) {
      // Lands on the last page of the previous chapter
      try {
        const previousChapter = await api.chapter(mangaId, chapter.previous_chapter)
        goTo(previousChapter.number, previousChapter.page_count)
      } catch (error) {
        setError(error)
      }
    }
  }, [chapter, goTo, mangaId])

  // Save progress shortly after the page settles, so flicking through pages sends one request
  useEffect(() => {
    if (!page) return
    const timer = setTimeout(() => {
      api.saveProgress(mangaId, chapterNumber, pageNumber).catch(() => {})
    }, SAVE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [page, mangaId, chapterNumber, pageNumber])

  useEffect(() => {
    if (!loaded) return
    const upcoming = chapter.pages.filter(
      (p) => p.number > pageNumber && p.number <= pageNumber + PRELOAD_AHEAD,
    )
    upcoming.forEach((p) => {
      const image = new Image()
      image.src = imageUrl(p.image_url)
    })
  }, [loaded, chapter, pageNumber])

  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0)
  }, [chapterNumber, pageNumber])

  const forward = rightToLeft ? previous : next
  const backward = rightToLeft ? next : previous

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "ArrowRight") forward()
      else if (event.key === "ArrowLeft") backward()
      else if (event.key === " " && !fitWidth) {
        event.preventDefault()
        next()
      } else if (event.key === "Escape") navigate(`/manga/${mangaId}`)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [forward, backward, next, fitWidth, navigate, mangaId])

  // Left third and right third turn pages, the middle shows the controls
  const onTap = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - bounds.left) / bounds.width
    if (x < 1 / 3) backward()
    else if (x > 2 / 3) forward()
    else setShowControls((shown) => !shown)
  }

  const onTouchStart = (event) => {
    if (event.touches.length !== 1) return (touchStart.current = null)
    touchStart.current = { x: event.touches[0].clientX, y: event.touches[0].clientY }
  }

  const onTouchEnd = (event) => {
    const start = touchStart.current
    touchStart.current = null
    if (!start) return
    const dx = event.changedTouches[0].clientX - start.x
    const dy = event.changedTouches[0].clientY - start.y
    if (Math.abs(dx) > SWIPE_DISTANCE && Math.abs(dx) > Math.abs(dy) * 1.5) {
      // The next page is dragged in from the side it's on: the right in left-to-right mode
      const towardsNext = rightToLeft ? dx > 0 : dx < 0
      towardsNext ? next() : previous()
      event.preventDefault() // Stops the tap handler also firing
    }
  }

  const barClass =
    "absolute left-0 right-0 bg-black/85 text-white transition-opacity duration-200 z-10 " +
    (showControls ? "opacity-100" : "opacity-0 pointer-events-none")

  return (
    <div className="fixed inset-0 bg-black text-white select-none">
      <div
        ref={scrollRef}
        className={`absolute inset-0 ${fitWidth ? "overflow-y-auto" : "overflow-hidden flex items-center justify-center"}`}
        onClick={onTap}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {error ? (
          <div className="h-full flex flex-col items-center justify-center gap-4 p-6 text-center">
            <p>{error.message}</p>
            <Link to={`/manga/${mangaId}`} className="px-4 py-2 bg-blue-600 rounded-md">
              Back to manga
            </Link>
          </div>
        ) : page ? (
          <img
            key={page.image_url}
            src={imageUrl(page.image_url)}
            alt={`Page ${pageNumber}`}
            draggable={false}
            className={fitWidth ? "w-full h-auto" : "max-w-full max-h-full object-contain"}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-gray-400">Loading…</div>
        )}
      </div>

      <div className={`${barClass} top-0 pt-[env(safe-area-inset-top)]`}>
        <div className="flex items-center gap-3 px-3 h-14">
          <Link to={`/manga/${mangaId}`} className="p-2 -ml-1 rounded-md hover:bg-white/10" aria-label="Back to manga">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{chapter?.manga_title}</p>
            <p className="truncate text-xs text-gray-400">{chapter?.title || `Chapter ${chapterNumber}`}</p>
          </div>
          <button
            onClick={() => setRightToLeft((value) => !value)}
            className="flex items-center gap-1 px-2 py-1.5 rounded-md text-xs hover:bg-white/10"
            aria-label="Reading direction"
          >
            <MoveHorizontal className="w-4 h-4" /> {rightToLeft ? "Right to left" : "Left to right"}
          </button>
          <button
            onClick={() => setFitWidth((value) => !value)}
            className="flex items-center gap-1 px-2 py-1.5 rounded-md text-xs hover:bg-white/10"
            aria-label="Fit"
          >
            <Maximize2 className="w-4 h-4" /> {fitWidth ? "Fit width" : "Fit screen"}
          </button>
        </div>
      </div>

      <div className={`${barClass} bottom-0 pb-[env(safe-area-inset-bottom)]`}>
        <div className="flex items-center gap-3 px-3 h-16">
          <button
            onClick={backward}
            className="p-2 rounded-md hover:bg-white/10"
            aria-label={rightToLeft ? "Next page" : "Previous page"}
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <input
            type="range"
            min={1}
            max={chapter?.page_count || 1}
            value={pageNumber}
            onChange={(event) => goTo(chapterNumber, Number(event.target.value))}
            className="flex-1 accent-blue-500"
            style={{ direction: rightToLeft ? "rtl" : "ltr" }}
            aria-label="Page"
          />
          <span className="text-sm tabular-nums w-20 text-center">
            {pageNumber} / {chapter?.page_count ?? "…"}
          </span>
          <button
            onClick={forward}
            className="p-2 rounded-md hover:bg-white/10"
            aria-label={rightToLeft ? "Previous page" : "Next page"}
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
