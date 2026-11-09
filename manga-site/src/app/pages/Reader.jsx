import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import {
  ArrowLeft,
  ArrowLeftRight,
  BookOpen,
  Flag,
  Info,
  Maximize2,
  MoveLeft,
  MoveRight,
  Pin,
  PinOff,
  ScrollText,
} from "lucide-react"
import { api, imageUrl } from "../lib/api"
import { getLocal, setLocal } from "../lib/storage"
import { keepScreenOn } from "../lib/native"
import { VerticalReader } from "../components/VerticalReader"
import { useAuth } from "../context/AuthContext"
import { useServerFeatures } from "../lib/features"
import * as offline from "../lib/offline"
import { FIT_MODES, STRIP_ASPECT, fitPageSize, getFitMode, setFitMode } from "../lib/pageFit"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu"

// Downloaded pages load from the phone; everything else from the server
const pageSrc = (page) => page.local_url ?? imageUrl(page.image_url)

const PRELOAD_AHEAD = 3
const SAVE_DELAY_MS = 600
// Like the classic reader: the outer 20% on each side turns the page, and a drag must
// travel this far (the page follows it a little) before it counts as a swipe
const EDGE_ZONE = 0.2
const SWIPE_DISTANCE = 40
const DRAG_START = 15
// Arrow keys scroll a page that's wider than the screen by this share of the screen before turning
const KEY_SCROLL = 0.8
const MODES = ["auto", "paged", "vertical"]

// Opens a few pages and reports whether they're long strips. Returns null if none could be measured.
async function looksLikeStrip(urls) {
  const sizes = await Promise.all(
    urls.map(
      (url) =>
        new Promise((resolve) => {
          const image = new Image()
          image.onload = () => resolve(image.naturalWidth ? image.naturalHeight / image.naturalWidth : null)
          image.onerror = () => resolve(null)
          image.src = url
        }),
    ),
  )
  const ratios = sizes.filter((ratio) => ratio !== null).sort((a, b) => a - b)
  if (!ratios.length) return null
  return ratios[Math.floor(ratios.length / 2)] >= STRIP_ASPECT
}

// Full-screen page reader. URL: /read/:mangaId/:chapter/:page
// Page turns replace the history entry, so Back leaves the reader instead of stepping through pages.
export function Reader() {
  const params = useParams()
  const mangaId = Number(params.mangaId)
  const chapterNumber = Number(params.chapter)
  const pageNumber = Number(params.page)
  const navigate = useNavigate()
  const { status } = useAuth()
  const offlineMode = status === "offline"
  const features = useServerFeatures()

  // A downloaded chapter is read from the phone even when online. Offline, previous and next
  // only go to other downloaded chapters.
  const loadChapter = useCallback(
    (number, signal) => {
      const local = offline.localChapter(mangaId, number, { offlineOnly: offlineMode })
      return local ? Promise.resolve(local) : api.chapter(mangaId, number, signal)
    },
    [mangaId, offlineMode],
  )

  const [chapter, setChapter] = useState(null)
  const [error, setError] = useState(null)
  const [showControls, setShowControls] = useState(false)
  // "always" keeps the bars on screen like the classic reader; "tap" hides them until the middle is tapped
  const [pinned, setPinned] = useState(() => getLocal("readerControls", "tap") === "always")
  const [chapters, setChapters] = useState([])
  const [glow, setGlow] = useState(null) // { side, id } restarts the edge animation each time
  const [dragOffset, setDragOffset] = useState(0)
  const hoverSide = useRef(null)
  // Direction: this series' own choice, then its details (ComicInfo), then the setting for all series
  const [seriesDirection, setSeriesDirection] = useState(() => getLocal(`readerDirection:${mangaId}`, null))
  const [hint, setHint] = useState(null) // { mode, direction } from the server
  const rightToLeft = (seriesDirection ?? hint?.direction ?? getLocal("readerDirection", "ltr")) === "rtl"
  const setRightToLeft = (update) => {
    const value = (typeof update === "function" ? update(rightToLeft) : update) ? "rtl" : "ltr"
    setLocal(`readerDirection:${mangaId}`, value)
    setSeriesDirection(value)
  }
  // Mode: "auto" uses the series' details, then the shape of its pages
  const [modeSetting, setModeSetting] = useState(() => {
    const saved = getLocal(`readerMode:${mangaId}`, "auto")
    return MODES.includes(saved) ? saved : "auto"
  })
  const [detected, setDetected] = useState(() => {
    const saved = getLocal(`readerDetected:${mangaId}`, null)
    return saved === null ? null : saved === "vertical"
  })
  const vertical =
    modeSetting === "vertical" ||
    (modeSetting === "auto" && (hint?.mode === "vertical" || (hint !== null && hint.mode === null && detected === true)))
  const stripRef = useRef(null)
  const [fitMode, setFitModeState] = useState(getFitMode)
  const chooseFitMode = (mode) => {
    setFitMode(mode)
    setFitModeState(mode)
  }
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
  useEffect(() => setLocal(`readerMode:${mangaId}`, modeSetting), [modeSetting, mangaId])
  useEffect(() => setLocal("readerControls", pinned ? "always" : "tap"), [pinned])

  // Chapter titles for the chapter picker
  useEffect(() => {
    const controller = new AbortController()
    const saved = offline.mangaInfo(mangaId)
    const use = (manga) => {
      setChapters(manga.chapters)
      setHint(manga.reading_hint ?? { mode: null, direction: null })
    }
    if (offlineMode && saved) use(saved)
    else
      api
        .manga(mangaId, controller.signal)
        .then(use)
        .catch((error) => {
          if (error.name === "AbortError") return
          if (saved) use(saved)
          else setHint({ mode: null, direction: null })
        })
    return () => controller.abort()
  }, [mangaId, offlineMode])

  const flash = (side) => setGlow({ side, id: Date.now() })

  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    loadChapter(chapterNumber, controller.signal)
      .then(setChapter)
      .catch((error) => error.name !== "AbortError" && setError(error))
    return () => controller.abort()
  }, [mangaId, chapterNumber, loadChapter])

  const loaded = chapter && chapter.manga_id === mangaId && chapter.number === chapterNumber
  const page = loaded ? chapter.pages.find((p) => p.number === pageNumber) : null

  // Auto mode without a hint: measure the first pages once per series and remember the answer
  const needsDetection = modeSetting === "auto" && hint !== null && hint.mode === null && detected === null
  useEffect(() => {
    if (!needsDetection || !loaded) return
    let cancelled = false
    looksLikeStrip(chapter.pages.slice(0, 3).map(pageSrc)).then((strip) => {
      if (cancelled || strip === null) return
      setLocal(`readerDetected:${mangaId}`, strip ? "vertical" : "paged")
      setDetected(strip)
    })
    return () => {
      cancelled = true
    }
  }, [needsDetection, loaded, chapter, mangaId])
  // Waiting for the hint or the measurement, so a webtoon doesn't flash up as single pages first
  const deciding = modeSetting === "auto" && (hint === null || needsDetection)

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
        const previousChapter = await loadChapter(chapter.previous_chapter)
        goTo(previousChapter.number, previousChapter.page_count)
      } catch (error) {
        setError(error)
      }
    }
  }, [chapter, goTo, mangaId, loadChapter])

  // Save progress shortly after the page settles, so flicking through pages sends one request
  // The last page of a chapter is always saved, even when it's left straight away, because
  // reaching it marks the chapter read
  const pageCountNow = loaded ? chapter.page_count : 0
  useEffect(() => {
    if (!page) return
    let sent = false
    const save = () => {
      sent = true
      offline.saveProgress(mangaId, chapterNumber, pageNumber, pageNumber >= pageCountNow)
    }
    const timer = setTimeout(save, SAVE_DELAY_MS)
    const lastPage = pageNumber >= pageCountNow
    return () => {
      clearTimeout(timer)
      if (!sent && lastPage) save()
    }
  }, [page, mangaId, chapterNumber, pageNumber, pageCountNow])

  useEffect(() => {
    if (!loaded || vertical) return
    const upcoming = chapter.pages.filter(
      (p) => p.number > pageNumber && p.number <= pageNumber + PRELOAD_AHEAD,
    )
    upcoming.forEach((p) => {
      const image = new Image()
      image.src = pageSrc(p)
    })
  }, [loaded, chapter, pageNumber, vertical])

  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0)
  }, [chapterNumber, pageNumber])

  const forward = rightToLeft ? previous : next
  const backward = rightToLeft ? next : previous

  // The page's display size comes from the fit mode (lib/pageFit.js) once the image has loaded
  const pageSize =
    viewport && page && natural?.url === pageSrc(page) ? fitPageSize(fitMode, natural, viewport) : null
  const scrollsDown = pageSize ? pageSize.height > viewport.height + 1 : fitMode === "width"
  const scrollsSideways = !!pageSize && pageSize.width > viewport.width + 1

  // A right-to-left page wider than the screen starts at its right edge, where reading begins
  useLayoutEffect(() => {
    const element = scrollRef.current
    if (element && scrollsSideways) element.scrollLeft = rightToLeft ? element.scrollWidth : 0
  }, [natural?.url, fitMode, scrollsSideways, rightToLeft])

  // How far a page wider than the screen can still scroll left (-1) or right (1)
  const sidewaysRoom = (direction) => {
    const element = scrollRef.current
    if (!element || !scrollsSideways) return 0
    return direction < 0 ? element.scrollLeft : element.scrollWidth - element.clientWidth - element.scrollLeft
  }

  useEffect(() => {
    const onKey = (event) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return
      // WASD work like the arrow keys, but not while a picker or the slider has focus
      const letter = event.key.length === 1 ? event.key.toLowerCase() : null
      if (letter && event.target.closest?.("input, select, textarea")) return
      if (vertical) {
        const down = ["ArrowDown", "ArrowRight", "PageDown", " "].includes(event.key) || letter === "s" || letter === "d"
        const up = ["ArrowUp", "ArrowLeft", "PageUp"].includes(event.key) || letter === "w" || letter === "a"
        if (down || up) {
          event.preventDefault()
          stripRef.current?.scrollByScreen(down ? 1 : -1)
        } else if (event.key === "Escape") navigate(`/manga/${mangaId}`)
        return
      }
      if (letter === "w" || letter === "s") {
        scrollRef.current?.scrollBy({ top: (letter === "w" ? -1 : 1) * 80 })
        return
      }
      const right = event.key === "ArrowRight" || letter === "d"
      const left = event.key === "ArrowLeft" || letter === "a"
      if (right || left) {
        // A page wider than the screen scrolls to its edge first, then the page turns
        const direction = right ? 1 : -1
        const element = scrollRef.current
        if (sidewaysRoom(direction) > 2) {
          event.preventDefault()
          element.scrollBy({ left: direction * element.clientWidth * KEY_SCROLL, behavior: "smooth" })
        } else right ? forward() : backward()
      } else if (event.key === " ") {
        // Space scrolls a tall page first, then turns to the next one at the bottom
        const element = scrollRef.current
        const atBottom = !element || element.scrollTop + element.clientHeight >= element.scrollHeight - 2
        if (scrollsDown && !atBottom) return
        if (fitMode === "width") return
        event.preventDefault()
        next()
      } else if (event.key === "Escape") navigate(`/manga/${mangaId}`)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  // Vertical mode reports the page in the middle of the screen; the URL follows it
  const onStripPage = useCallback((number) => goTo(position.current.chapter, number), [goTo])
  const onStripFinished = useCallback(() => {
    if (chapter?.next_chapter != null) goTo(chapter.next_chapter, 1)
  }, [chapter, goTo])
  const nextChapterInfo = chapters.find((item) => item.number === chapter?.next_chapter)
  const fitModeLabel = FIT_MODES.find((mode) => mode.id === fitMode).label
  const modeLabel =
    modeSetting === "auto" ? `Auto (${vertical ? "scroll" : "pages"})` : modeSetting === "vertical" ? "Scroll" : "Pages"

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
      // A page wider than the screen scrolls sideways until it reaches its edge; only then
      // does a drag turn the page. Dragging left moves the view right.
      if (sidewaysRoom(dx < 0 ? 1 : -1) > 2) return (touchStart.current = null)
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
    "bg-white/10 hover:bg-white/15 rounded-md px-2 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-brand-500"
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
          onClick={() => setModeSetting((mode) => MODES[(MODES.indexOf(mode) + 1) % MODES.length])}
          className={`${iconButton} flex items-center gap-1.5 text-xs`}
          aria-label={`Reading mode: ${modeLabel}`}
          title="Reading mode for this series: auto, single pages, or vertical scroll (webtoon)"
        >
          {vertical ? <ScrollText className="bounce-icon w-4 h-4" /> : <BookOpen className="bounce-icon w-4 h-4" />}
          <span className="hidden sm:inline">{modeLabel}</span>
        </button>
        <button
          onClick={() => setRightToLeft((value) => !value)}
          hidden={vertical}
          className={`${iconButton} flex items-center gap-1.5 text-xs`}
          aria-label={rightToLeft ? "Reading right to left" : "Reading left to right"}
          title="Page direction for this series"
        >
          <ArrowLeftRight className="bounce-icon w-4 h-4" />
          <span className="hidden sm:inline">{rightToLeft ? "Right to left" : "Left to right"}</span>
        </button>
        {!vertical && (
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger
              className={`${iconButton} flex items-center gap-1.5 text-xs focus:outline-none`}
              aria-label={`Page size: ${fitModeLabel}`}
              title="Page size"
            >
              <Maximize2 className="bounce-icon w-4 h-4" />
              <span className="hidden sm:inline">{fitModeLabel}</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64 bg-gray-900 text-white border-white/10">
              <DropdownMenuRadioGroup value={fitMode} onValueChange={chooseFitMode}>
                {FIT_MODES.map((mode) => (
                  <DropdownMenuRadioItem
                    key={mode.id}
                    value={mode.id}
                    className="items-start focus:bg-white/10 focus:text-white [&>span:first-child]:top-3"
                  >
                    <div>
                      <p>{mode.label}</p>
                      <p className="text-xs text-gray-400">{mode.description}</p>
                    </div>
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
        <button
          onClick={() => {
            setPinned((value) => !value)
            setShowControls(true)
          }}
          className={`${iconButton} flex items-center gap-1.5 text-xs ${pinned ? "text-brand-400" : ""}`}
          aria-pressed={pinned}
          aria-label="Keep controls visible"
          title={pinned ? "Controls always visible" : "Controls hide until you tap the middle"}
        >
          {pinned ? <Pin className="bounce-icon w-4 h-4" /> : <PinOff className="bounce-icon w-4 h-4" />}
          <span className="hidden sm:inline">{pinned ? "Always show" : "Tap to show"}</span>
        </button>
        {features.feedback && !offlineMode && (
          <Link
            to={`/feedback?kind=content_problem&manga=${mangaId}&chapter=${chapterNumber}`}
            state={{ from: `/read/${mangaId}/${chapterNumber}/${pageNumber}` }}
            className={`${iconButton} flex items-center gap-1.5 text-xs`}
            aria-label="Report a problem with this chapter"
            title="Report a problem with this chapter (missing or broken pages…)"
          >
            <Flag className="bounce-icon w-4 h-4" />
          </Link>
        )}
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
          className="w-full accent-brand-500"
          style={{ direction: rightToLeft && !vertical ? "rtl" : "ltr" }}
          aria-label="Page slider"
        />
      </div>
      <div className="flex items-center justify-center gap-1 sm:gap-2 px-2 sm:px-3 h-12">
        <Link to={`/manga/${mangaId}`} className={iconButton} aria-label="Manga details" title="Manga details">
          <Info className="bounce-icon w-5 h-5" />
        </Link>
        <button
          onClick={backward}
          hidden={vertical}
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
          hidden={vertical}
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
        {vertical && loaded && !error && (
          <VerticalReader
            ref={stripRef}
            chapter={chapter}
            pageNumber={pageNumber}
            pageUrl={pageSrc}
            onPageChange={onStripPage}
            onFinished={chapter.next_chapter != null ? onStripFinished : null}
            nextChapterLabel={
              chapter.next_chapter != null
                ? nextChapterInfo?.title || `chapter ${chapter.next_chapter}`
                : null
            }
            onTap={() => !pinned && setShowControls((shown) => !shown)}
          />
        )}
        <div
          ref={scrollRef}
          hidden={vertical && loaded && !error}
          className={`absolute inset-0 flex ${
            fitMode === "height" ? "overflow-x-auto overflow-y-hidden" : "overflow-x-hidden overflow-y-auto"
          }`}
          style={{
            touchAction: scrollsSideways ? "pan-x pinch-zoom" : scrollsDown ? "pan-y pinch-zoom" : "pinch-zoom",
          }}
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
              <Link to={`/manga/${mangaId}`} className="px-4 py-2 bg-brand-600 rounded-md">
                Back to manga
              </Link>
            </div>
          ) : page && !deciding ? (
            <img
              key={pageSrc(page)}
              src={pageSrc(page)}
              alt={`Page ${pageNumber}`}
              draggable={false}
              onLoad={(event) =>
                setNatural({
                  url: pageSrc(page),
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                })
              }
              // m-auto centers a page smaller than the screen and keeps a bigger one scrollable from its start.
              // Until the image's size is known, CSS gives a close guess.
              className={
                pageSize
                  ? "m-auto shrink-0 max-w-none"
                  : fitMode === "width"
                    ? "m-auto shrink-0 w-full h-auto"
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
