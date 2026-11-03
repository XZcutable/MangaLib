import { createContext, useContext, useEffect, useState } from "react"
const ThemeContext = createContext(undefined)
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("theme")
    return saved || "dark"
  })
  useEffect(() => {
    localStorage.setItem("theme", theme)
  }, [theme])
  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"))
  }
  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
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
