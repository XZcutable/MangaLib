import { useEffect, useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { chooseBanner } from "../lib/scenes"
import { TenmaBackdrop } from "./TenmaBackdrop"

function useViewport() {
  const read = () => ({ vw: window.innerWidth, vh: window.innerHeight })
  const [size, setSize] = useState(read)
  useEffect(() => {
    const update = () => setSize(read())
    window.addEventListener("resize", update)
    return () => window.removeEventListener("resize", update)
  }, [])
  return size
}

// The banner behind the page (see lib/scenes.js), or null when the setting is off or there's no room.
// Its `inset` is the padding that keeps the page's content clear of the art.
export function useScene() {
  const { theme, pageBackground } = useTheme()
  const { vw, vh } = useViewport()
  if (pageBackground !== "illustrated") return null
  return chooseBanner({ dark: theme === "dark", vw, vh })
}

// Fixed behind the page; the parent needs `isolate` so it sits above the page's background color
export function SceneImage({ scene }) {
  // Which image has loaded, so it fades in once; a cached image may already be complete when it mounts
  const [loadedSrc, setLoadedSrc] = useState(null)
  if (!scene) return null
  const loaded = loadedSrc === scene.src
  return (
    <img
      key={scene.src}
      src={scene.src}
      alt=""
      aria-hidden="true"
      decoding="async"
      draggable={false}
      ref={(image) => image?.complete && image.naturalWidth > 0 && loadedSrc !== scene.src && setLoadedSrc(scene.src)}
      onLoad={() => setLoadedSrc(scene.src)}
      className={`fixed inset-0 -z-10 h-full w-full object-cover pointer-events-none select-none transition-opacity duration-300 ${
        loaded ? "opacity-100" : "opacity-0"
      }`}
    />
  )
}

// What goes behind a page, by the Appearance setting: a scene, the faint Tenma figure, or nothing
export function PageBackground({ scene }) {
  const { pageBackground } = useTheme()
  if (pageBackground === "simple") return <TenmaBackdrop />
  return <SceneImage scene={scene} />
}
