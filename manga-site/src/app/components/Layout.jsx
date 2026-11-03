import { Outlet } from "react-router"
import { Navbar } from "./Navbar"
import { Footer } from "./Footer"
import { useTheme } from "../context/ThemeContext"
export function Layout() {
  const { theme } = useTheme()
  return (
    <div
      className={`min-h-screen flex flex-col ${
        theme === "dark" ? "bg-gray-950" : "bg-gray-50"
      }`}
    >
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
