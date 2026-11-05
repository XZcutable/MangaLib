// Tenma, the project mascot. The art lives in src/assets/tenma, one WebP per pose, made from the
// approved drawings by `pnpm tenma:assets`. Poses are listed in Tenma/poses.toml at the repo root.
// A pose that hasn't been drawn yet falls back to the main one, so art can arrive one pose at a time.
const ART = Object.fromEntries(
  Object.entries(import.meta.glob("../../assets/tenma/*.webp", { eager: true, import: "default" })).map(
    ([path, url]) => [path.split("/").pop().replace(/\.webp$/, ""), url],
  ),
)

export function tenmaArt(pose) {
  return ART[pose] ?? ART.main
}

export function hasTenmaPose(pose) {
  return pose in ART
}

const SIZES = {
  sm: "h-28",
  md: "h-40",
  lg: "h-64",
  xl: "h-80",
}

// Decorative only: the text next to her always says what's going on
export function Tenma({ pose = "main", size = "md", className = "" }) {
  const src = tenmaArt(pose)
  if (!src) return null
  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      loading="lazy"
      decoding="async"
      draggable={false}
      className={`${SIZES[size] ?? size} w-auto max-w-full object-contain select-none pointer-events-none ${className}`}
    />
  )
}
