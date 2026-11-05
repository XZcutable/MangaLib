import { createContext, useContext, useEffect, useState } from "react"
import { getLocal, setLocal } from "../lib/storage"

// Accent colors for buttons, links and highlights. The values live in styles/brand.css.
export const ACCENTS = [
  { id: "tenma", label: "Tenma", swatch: "oklch(52.5% 0.24 307.6)" },
  { id: "blue", label: "Blue", swatch: "oklch(54.6% 0.245 262.881)" },
  { id: "purple", label: "Purple", swatch: "oklch(55.8% 0.288 302.321)" },
  { id: "red", label: "Red", swatch: "oklch(57.7% 0.245 27.325)" },
]

const DEFAULT_ACCENT = "tenma"

const ThemeContext = createContext(undefined)

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => getLocal("theme", "dark"))
  const [accent, setAccentState] = useState(() => {
    const saved = getLocal("accent", DEFAULT_ACCENT)
    const initial = ACCENTS.some((option) => option.id === saved) ? saved : DEFAULT_ACCENT
    // Set before the first paint so the page doesn't flash another color
    document.documentElement.dataset.accent = initial
    return initial
  })

  // Tenma's figure in the page background (components/TenmaBackdrop.jsx)
  const [showMascot, setShowMascot] = useState(() => getLocal("showMascot", "true") !== "false")

  useEffect(() => setLocal("theme", theme), [theme])
  useEffect(() => setLocal("showMascot", String(showMascot)), [showMascot])
  useEffect(() => {
    setLocal("accent", accent)
    document.documentElement.dataset.accent = accent
  }, [accent])

  const toggleTheme = () => setTheme((prev) => (prev === "light" ? "dark" : "light"))

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, accent, setAccent: setAccentState, showMascot, setShowMascot }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return context
}
