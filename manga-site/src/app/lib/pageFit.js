import { getLocal, setLocal } from "./storage"

// Pages at least this many times taller than wide are a webtoon-style strip
export const STRIP_ASPECT = 2
// Smart fit shows the whole page unless that would make it shorter than this (CSS px),
// e.g. a phone held sideways. Then it fills the width and scrolls down instead.
export const MIN_READABLE_HEIGHT = 500

export const FIT_MODES = [
  {
    id: "smart",
    label: "Smart fit",
    description: "Whole page, but long strips and very short screens fill the width and scroll.",
  },
  { id: "screen", label: "Fit screen", description: "Always the whole page, never scrolls." },
  { id: "width", label: "Fit width", description: "Fills the width and scrolls down." },
  { id: "height", label: "Fit height", description: "Fills the height; wide pages scroll sideways." },
]
const IDS = FIT_MODES.map((mode) => mode.id)

// "readerFit" was the old setting ("screen" or "width"). Its "screen" became Smart fit,
// so the new setting has its own key.
export function getFitMode() {
  const saved = getLocal("readerPageFit", null)
  if (IDS.includes(saved)) return saved
  return getLocal("readerFit", null) === "width" ? "width" : "smart"
}

export function setFitMode(mode) {
  setLocal("readerPageFit", mode)
}

// Display size (CSS px) of a page of `natural` size in an area of `area` size
export function fitPageSize(mode, natural, area) {
  const { width: naturalWidth, height: naturalHeight } = natural
  const { width: areaWidth, height: areaHeight } = area
  const byWidth = { width: areaWidth, height: (areaWidth * naturalHeight) / naturalWidth }
  const byHeight = { width: (areaHeight * naturalWidth) / naturalHeight, height: areaHeight }
  const whole = byWidth.height <= areaHeight ? byWidth : byHeight

  if (mode === "width") return byWidth
  if (mode === "height") return byHeight
  if (mode === "screen") return whole
  const strip = naturalHeight / naturalWidth >= STRIP_ASPECT
  if (strip || (whole.height < MIN_READABLE_HEIGHT && byWidth.height > whole.height)) return byWidth
  return whole
}
