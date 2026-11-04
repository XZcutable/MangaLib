import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { ArrowLeft, ArrowLeftRight, Info, Maximize2, MoveLeft, MoveRight, Pin, PinOff } from "lucide-react"
import { api, imageUrl } from "../lib/api"
import { getLocal, setLocal } from "../lib/storage"
import { keepScreenOn } from "../lib/native"

const PRELOAD_AHEAD = 3
const SAVE_DELAY_MS = 600
// Like the classic reader: the outer 20% on each side turns the page, and a drag must
// travel this far (the page follows it a little) before it counts as a swipe
const EDGE_ZONE = 0.2
const SWIPE_DISTANCE = 40
const DRAG_START = 15

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
  // "always" keeps the bars on screen like the classic reader; "tap" hides them until the middle is tapped
  const [pinned, setPinned] = useState(() => getLocal("readerControls", "tap") === "always")
  const [chapters, setChapters] = useState([])
  const [glow, setGlow] = useState(null) // { side, id } restarts the edge animation each time
  const [dragOffset, setDragOffset] = useState(0)
  const hoverSide = useRef(null)
  const [rightToLeft, setRightToLeft] = useState(() => getLocal("readerDirection", "ltr") === "rtl")
  const [fitWidth, setFitWidth] = useState(() => getLocal("readerFit", "screen") === "width")
  const touchStart = useRef(null)
  const scrollRef = useRef(null)
  const [viewport, setViewport] = useState(null) // size of the page area
  const [natural, setNatural] = useState(null) // { url, width, height } of the loaded image

  useEffect(() => {
    const element = scrollRef.current
    if (!element) return
    const observer = new ResizeObserver(() =>
      setViewport({ width: element.clientWidth, height: element.clientHeight }),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    keepScreenOn(true)
    return () => keepScreenOn(false)
  }, [])
  useEffect(() => setLocal("readerDirection", rightToLeft ? "rtl" : "ltr"), [rightToLeft])
  useEffect(() => setLocal("readerFit", fitWidth ? "width" : "screen"), [fitWidth])
  useEffect(() => setLocal("readerControls", pinned ? "always" : "tap"), [pinned])

  // Chapter titles for the chapter picker
  useEffect(() => {
    const controller = new AbortController()
    api
      .manga(mangaId, controller.signal)
      .then((manga) => setChapters(manga.chapters))
      .catch(() => {})
    return () => controller.abort()
  }, [mangaId])

  const flash = (side) => setGlow({ side, id: Date.now() })

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

  // Fit screen: when the reader area is at least as tall as the page, the page is scaled to fill
  // the height (but never wider than the screen). When the area is shorter, the page is shown at
  // the screen width, or its own width if that's smaller, and scrolls down.
  let pageSize = null
  if (!fitWidth && viewport && page && natural?.url === page.image_url) {
    const { width: areaWidth, height: areaHeight } = viewport
    if (areaHeight >= natural.height) {
      const scale = Math.min(areaHeight / natural.height, areaWidth / natural.width)
      pageSize = { width: natural.width * scale, height: natural.height * scale }
    } else {
      const width = Math.min(areaWidth, natural.width)
      pageSize = { width, height: (width * natural.height) / natural.width }
    }
  }
  const pageScrolls = fitWidth || (pageSize && viewport && pageSize.height > viewport.height + 1)

  useEffect(() => {
    const onKey = (event) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return
      // WASD work like the arrow keys, but not while a picker or the slider has focus
      const letter = event.key.length === 1 ? event.key.toLowerCase() : null
      if (letter && event.target.closest?.("input, select, textarea")) return
      if (letter === "w" || letter === "s") {
        scrollRef.current?.scrollBy({ top: (letter === "w" ? -1 : 1) * 80 })
        return
      }
      if (event.key === "ArrowRight" || letter === "d") forward()
      else if (event.key === "ArrowLeft" || letter === "a") backward()
      else if (event.key === " ") {
        // Space scrolls a tall page first, then turns to the next one at the bottom
        const element = scrollRef.current
        const atBottom = !element || element.scrollTop + element.clientHeight >= element.scrollHeight - 2
        if (pageScrolls && !atBottom) return
        if (fitWidth) return
        event.preventDefault()
        next()
      } else if (event.key === "Escape") navigate(`/manga/${mangaId}`)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [forward, backward, next, fitWidth, pageScrolls, navigate, mangaId])

  const zoneAt = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - bounds.left) / bounds.width
    return x < EDGE_ZONE ? "left" : x > 1 - EDGE_ZONE ? "right" : null
  }

  // The edges turn pages, the middle shows or hides the controls
  const onTap = (event) => {
    const side = zoneAt(event)
    if (side === "left") {
      flash("left")
      backward()
    } else if (side === "right") {
      flash("right")
      forward()
    } else if (!pinned) {
      setShowControls((shown) => !shown)
    }
  }

  // With a mouse, the edge glows as the pointer moves onto it, so it's clear clicking there turns the page
  const onMouseMove = (event) => {
    const side = zoneAt(event)
    if (side !== hoverSide.current) {
      hoverSide.current = side
      if (side) flash(side)
    }
    event.currentTarget.style.cursor = side ? "pointer" : "default"
  }

  const onTouchStart = (event) => {
    if (event.touches.length !== 1) return (touchStart.current = null)
    touchStart.current = {
      x: event.touches[0].clientX,
      y: event.touches[0].clientY,
      dragging: false,
      glowed: false,
    }
  }

  // The page follows a sideways drag a little and the edge glows once the drag is long enough to turn it
  const onTouchMove = (event) => {
    const start = touchStart.current
    if (!start || event.touches.length !== 1) return
    const dx = event.touches[0].clientX - start.x
    const dy = event.touches[0].clientY - start.y
    if (!start.dragging) {
      // Mostly vertical: the reader is scrolling a long page, not turning it
      if (Math.abs(dy) > DRAG_START && Math.abs(dy) > Math.abs(dx)) return (touchStart.current = null)
      if (Math.abs(dx) < DRAG_START) return
      start.dragging = true
    }
    setDragOffset(Math.max(-SWIPE_DISTANCE, Math.min(SWIPE_DISTANCE, dx)))
    if (!start.glowed && Math.abs(dx) >= SWIPE_DISTANCE) {
      start.glowed = true
      flash(dx > 0 ? "left" : "right")
    }
  }

  const onTouchEnd = (event) => {
    const start = touchStart.current
    touchStart.current = null
    setDragOffset(0)
    if (!start?.dragging) return
    const dx = event.changedTouches[0].clientX - start.x
    if (Math.abs(dx) >= SWIPE_DISTANCE) {
      // The next page is dragged in from the side it's on: the right in left-to-right mode
      const towardsNext = rightToLeft ? dx > 0 : dx < 0
      towardsNext ? next() : previous()
    }
    event.preventDefault() // A drag isn't a tap, so the tap handler shouldn't also run
  }

  const controlsVisible = pinned || showControls
  const pageCount = chapter?.page_count ?? 0
  const iconButton = "bounce-on-hover p-2 rounded-md hover:bg-white/10 shrink-0"
  const select =
    "bg-white/10 hover:bg-white/15 rounded-md px-2 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-blue-500"
  // Pinned bars take their own space like the classic reader; otherwise they float over the page
  const barClass = pinned
    ? "relative bg-gray-950 text-white z-10 shrink-0"
    : "absolute left-0 right-0 bg-black/85 text-white transition-opacity duration-200 z-10 " +
      (controlsVisible ? "opacity-100" : "opacity-0 pointer-events-none")

  const topBar = (
    <div className={`${barClass} top-0 pt-[env(safe-area-inset-top)]`}>
      <div className="flex items-center gap-1 sm:gap-2 px-2 sm:px-3 h-14">
        <Link to={`/manga/${mangaId}`} className={iconButton} aria-label="Back to manga" title="Back to manga">
          <ArrowLeft className="bounce-icon w-5 h-5" />
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{chapter?.manga_title}</p>
          <p className="truncate text-xs text-gray-400">{chapter?.title || `Chapter ${chapterNumber}`}</p>
        </div>
        <button
          onClick={() => setRightToLeft((value) => !value)}
          className={`${iconButton} flex items-center gap-1.5 text-xs`}
          aria-label={rightToLeft ? "Reading right to left" : "Reading left to right"}
          title="Page direction"
        >
          <ArrowLeftRight className="bounce-icon w-4 h-4" />
          <span className="hidden sm:inline">{rightToLeft ? "Right to left" : "Left to right"}</span>
        </button>
        <button
          onClick={() => setFitWidth((value) => !value)}
          className={`${iconButton} flex items-center gap-1.5 text-xs`}
          aria-label={fitWidth ? "Fit width" : "Fit screen"}
          title="Page size"
        >
          <Maximize2 className="bounce-icon w-4 h-4" />
          <span className="hidden sm:inline">{fitWidth ? "Fit width" : "Fit screen"}</span>
        </button>
        <button
          onClick={() => {
            setPinned((value) => !value)
            setShowControls(true)
          }}
          className={`${iconButton} flex items-center gap-1.5 text-xs ${pinned ? "text-blue-400" : ""}`}
          aria-pressed={pinned}
          aria-label="Keep controls visible"
          title={pinned ? "Controls always visible" : "Controls hide until you tap the middle"}
        >
          {pinned ? <Pin className="bounce-icon w-4 h-4" /> : <PinOff className="bounce-icon w-4 h-4" />}
          <span className="hidden sm:inline">{pinned ? "Always show" : "Tap to show"}</span>
        </button>
      </div>
    </div>
  )

  // Like the classic reader's footer: info, arrows, and pickers to jump to any page or chapter
  const bottomBar = (
    <div className={`${barClass} bottom-0 pb-[env(safe-area-inset-bottom)]`}>
      <div className="px-3 pt-2">
        <input
          type="range"
          min={1}
          max={pageCount || 1}
          value={pageNumber}
          onChange={(event) => goTo(chapterNumber, Number(event.target.value))}
          className="w-full accent-blue-500"
          style={{ direction: rightToLeft ? "rtl" : "ltr" }}
          aria-label="Page slider"
        />
      </div>
      <div className="flex items-center justify-center gap-1 sm:gap-2 px-2 sm:px-3 h-12">
        <Link to={`/manga/${mangaId}`} className={iconButton} aria-label="Manga details" title="Manga details">
          <Info className="bounce-icon w-5 h-5" />
        </Link>
        <button
          onClick={backward}
          className={`${iconButton} hidden sm:block`}
          aria-label={rightToLeft ? "Next page" : "Previous page"}
          title={rightToLeft ? "Next page" : "Previous page"}
        >
          <MoveLeft className="bounce-icon w-5 h-5" />
        </button>
        <select
          className={select}
          value={pageNumber}
          onChange={(event) => goTo(chapterNumber, Number(event.target.value))}
          aria-label="Page"
          disabled={!pageCount}
        >
          {Array.from({ length: pageCount || 1 }, (_, index) => (
            <option key={index + 1} value={index + 1} className="bg-gray-900">
              {index + 1} / {pageCount || "…"}
            </option>
          ))}
        </select>
        <button
          onClick={forward}
          className={`${iconButton} hidden sm:block`}
          aria-label={rightToLeft ? "Previous page" : "Next page"}
          title={rightToLeft ? "Previous page" : "Next page"}
        >
          <MoveRight className="bounce-icon w-5 h-5" />
        </button>
        {chapters.length > 1 && (
          <select
            className={`${select} min-w-0 max-w-[45vw] sm:max-w-xs truncate`}
            value={chapterNumber}
            onChange={(event) => goTo(Number(event.target.value), 1)}
            aria-label="Chapter"
          >
            {chapters.map((item) => (
              <option key={item.number} value={item.number} className="bg-gray-900">
                Chapter {item.number}
                {item.title ? ` · ${item.title}` : ""}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black text-white select-none flex flex-col">
      {pinned && topBar}
      <div className="relative flex-1 min-h-0 overflow-hidden">
        <div
          ref={scrollRef}
          className={`absolute inset-0 overflow-x-hidden ${fitWidth ? "overflow-y-auto" : "overflow-y-auto flex"}`}
          style={{ touchAction: pageScrolls ? "pan-y pinch-zoom" : "pinch-zoom" }}
          onClick={onTap}
          onMouseMove={onMouseMove}
          onMouseLeave={() => (hoverSide.current = null)}
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
          onTouchCancel={() => {
            touchStart.current = null
            setDragOffset(0)
          }}
        >
          {error ? (
            <div className="w-full h-full flex flex-col items-center justify-center gap-4 p-6 text-center">
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
              onLoad={(event) =>
                setNatural({
                  url: page.image_url,
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                })
              }
              // m-auto centers a page smaller than the screen and keeps a taller one scrollable from its top
              className={
                fitWidth
                  ? "w-full h-auto"
                  : pageSize
                    ? "m-auto shrink-0"
                    : "m-auto max-w-full max-h-full object-contain"
              }
              style={{
                ...(pageSize && { width: pageSize.width, height: pageSize.height }),
                transform: dragOffset ? `translateX(${dragOffset}px)` : undefined,
                transition: dragOffset ? "none" : "transform 150ms ease-out",
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">Loading…</div>
          )}
        </div>
        {glow && <div key={glow.id} className={`edge-glow edge-glow-${glow.side}`} aria-hidden="true" />}
        {!pinned && topBar}
        {!pinned && bottomBar}
      </div>
      {pinned && bottomBar}
    </div>
  )
}
