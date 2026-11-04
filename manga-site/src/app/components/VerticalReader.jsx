import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react"

// Height/width used for pages that haven't loaded yet, until real pages give a better guess
const DEFAULT_ASPECT = 1.5

// Webtoon-style reading: every page of the chapter stacked at full width, scrolled continuously.
// The page crossing the middle of the screen is the current one; it's reported with onPageChange.
// Scrolling past the end of the chapter (through the "keep scrolling" area) opens the next one.
export const VerticalReader = forwardRef(function VerticalReader(
  { chapter, pageNumber, pageUrl, onPageChange, onFinished, onTap, nextChapterLabel },
  ref,
) {
  const scrollRef = useRef(null)
  const pageRefs = useRef(new Map())
  const reported = useRef(pageNumber)
  const [aspects, setAspects] = useState({}) // page number -> height/width once loaded
  const endRef = useRef(null)

  useImperativeHandle(ref, () => ({
    // For the keyboard: a screen at a time, keeping a little overlap
    scrollByScreen(direction) {
      const element = scrollRef.current
      if (element) element.scrollBy({ top: direction * element.clientHeight * 0.85, behavior: "smooth" })
    },
  }))

  // Placeholders take the typical shape of this chapter's pages, so the scroll position stays put
  const known = Object.values(aspects).sort((a, b) => a - b)
  const typicalAspect = known.length ? known[Math.floor(known.length / 2)] : DEFAULT_ASPECT

  // Jump to a page chosen elsewhere (slider, picker, opening at the saved page), but not when the
  // change came from scrolling here
  useEffect(() => {
    if (pageNumber === reported.current) return
    reported.current = pageNumber
    pageRefs.current.get(pageNumber)?.scrollIntoView({ block: "start" })
  }, [pageNumber])

  // A new chapter opens at the requested page (usually the top)
  useEffect(() => {
    reported.current = pageNumber
    const element = pageRefs.current.get(pageNumber)
    if (pageNumber > 1 && element) element.scrollIntoView({ block: "start" })
    else scrollRef.current?.scrollTo(0, 0)
    // Only when the chapter changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapter.manga_id, chapter.number])

  // Track the page crossing the middle of the screen
  useEffect(() => {
    const root = scrollRef.current
    if (!root) return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          const number = Number(entry.target.dataset.page)
          if (number !== reported.current) {
            reported.current = number
            onPageChange(number)
          }
        }
      },
      { root, rootMargin: "-50% 0px -50% 0px" },
    )
    pageRefs.current.forEach((element) => observer.observe(element))
    return () => observer.disconnect()
  }, [chapter, onPageChange])

  // Reaching the bottom of the "keep scrolling" area moves on to the next chapter
  useEffect(() => {
    const root = scrollRef.current
    const end = endRef.current
    if (!root || !end || !onFinished) return
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && entry.intersectionRatio >= 0.99 && onFinished(),
      { root, threshold: [0.99] },
    )
    observer.observe(end)
    return () => observer.disconnect()
  }, [chapter, onFinished])

  return (
    <div
      ref={scrollRef}
      className="absolute inset-0 overflow-y-auto overflow-x-hidden"
      style={{ touchAction: "pan-y pinch-zoom", overflowAnchor: "auto" }}
      onClick={onTap}
    >
      <div className="mx-auto w-full max-w-3xl">
        {chapter.pages.map((page) => {
          const aspect = aspects[page.number]
          return (
            <img
              key={page.number}
              ref={(element) => {
                if (element) pageRefs.current.set(page.number, element)
                else pageRefs.current.delete(page.number)
              }}
              data-page={page.number}
              src={pageUrl(page)}
              alt={`Page ${page.number}`}
              loading="lazy"
              decoding="async"
              draggable={false}
              onLoad={(event) => {
                const { naturalWidth, naturalHeight } = event.currentTarget
                if (naturalWidth)
                  setAspects((previous) => ({ ...previous, [page.number]: naturalHeight / naturalWidth }))
              }}
              className="block w-full h-auto"
              style={aspect ? undefined : { aspectRatio: `1 / ${typicalAspect}`, background: "#111" }}
            />
          )
        })}
        <div
          ref={endRef}
          className="h-[45vh] flex flex-col items-center justify-center gap-2 text-gray-400 text-sm text-center px-6"
        >
          <p className="text-white">End of {chapter.title || `chapter ${chapter.number}`}</p>
          <p>{nextChapterLabel ? `Keep scrolling for ${nextChapterLabel}` : "That's the last chapter"}</p>
        </div>
      </div>
    </div>
  )
})
