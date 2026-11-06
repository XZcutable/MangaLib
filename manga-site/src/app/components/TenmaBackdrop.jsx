import { useTheme } from "../context/ThemeContext"
import { hasTenmaPose, tenmaArt } from "./Tenma"

// A faint Tenma figure in the corner of the page, behind everything. It uses her outline as a mask
// filled with the accent color, so it follows the accent and never competes with covers or text.
// The parent needs `isolate` so the figure sits above the page background but below the content.
// Shown when Settings → Appearance → Page background is "Simple" (components/PageBackground.jsx).
export function TenmaBackdrop() {
  const { theme } = useTheme()
  // The line-art "silhouette" pose is made for this; until it exists, the main pose's outline is used
  const src = tenmaArt(hasTenmaPose("silhouette") ? "silhouette" : "main")
  if (!src) return null
  const mask = {
    maskImage: `url("${src}")`,
    WebkitMaskImage: `url("${src}")`,
    maskSize: "contain",
    WebkitMaskSize: "contain",
    maskRepeat: "no-repeat",
    WebkitMaskRepeat: "no-repeat",
    maskPosition: "bottom right",
    WebkitMaskPosition: "bottom right",
  }
  return (
    <div
      aria-hidden="true"
      style={mask}
      className={`fixed -z-10 pointer-events-none bottom-0 right-0 h-[45vh] w-[30vh] lg:h-[75vh] lg:w-[50vh] lg:right-6 bg-brand-500 ${
        theme === "dark" ? "opacity-[0.07] lg:opacity-[0.09]" : "opacity-[0.08] lg:opacity-[0.1]"
      }`}
    />
  )
}
