// The illustrated page background: the banner, a frame of art at both edges with a clear middle.
// Made from Tenma/backgrounds/banner(-dark).png by `pnpm tenma:assets`. It covers the screen and the
// page content gets equal padding on both sides, so the content stays centered inside the clear middle.
const IMAGES = Object.fromEntries(
  Object.entries(import.meta.glob("../../assets/backgrounds/banner*.webp", { eager: true, import: "default" })).map(
    ([path, url]) => [path.split("/").pop().replace(/\.webp$/, ""), url],
  ),
)

const ASPECT = 16 / 9
const GAP = 24 // px between the art and the content
const MIN_CONTENT = 560 // the banner gives way when the content would be narrower than this

// Where the art ends, as fractions of the image width
const ART = {
  banner: { left: 0.17, right: 0.84 },
  "banner-dark": { left: 0.2, right: 0.8 },
}

// The banner for a screen of vw x vh, with the padding that keeps content clear of its art, or null
// when there's no room (phones)
export function chooseBanner({ dark, vw, vh }) {
  const key = dark && IMAGES["banner-dark"] ? "banner-dark" : "banner"
  if (!IMAGES[key]) return null
  const width = Math.max(vw, vh * ASPECT)
  const cropped = (width - vw) / 2
  const artLeft = ART[key].left * width - cropped
  const artRight = ART[key].right * width - cropped
  const inset = Math.max(artLeft > 0 ? artLeft + GAP : 0, artRight < vw ? vw - artRight + GAP : 0)
  if (vw - 2 * inset < MIN_CONTENT) return null
  return { src: IMAGES[key], inset: Math.round(inset) }
}
