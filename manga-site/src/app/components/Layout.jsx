import { Outlet } from "react-router"
import { Navbar } from "./Navbar"
import { Footer } from "./Footer"
import { PageBackground, useScene } from "./PageBackground"
import { useTheme } from "../context/ThemeContext"
import { useAuth } from "../context/AuthContext"

export function Layout() {
  const { theme } = useTheme()
  const { status, server, retry } = useAuth()
  const scene = useScene()
  return (
    <div
      className={`relative isolate min-h-screen flex flex-col ${
        theme === "dark" ? "bg-gray-950" : "bg-gray-50"
      }`}
    >
      <PageBackground scene={scene} />
      <Navbar />
      {status === "offline" && (
        <div className={`bg-amber-500/15 text-sm px-4 py-2 flex items-center justify-between gap-3 ${
            theme === "dark" ? "text-amber-300" : "text-amber-700"
          }`}>
          <span>Offline: can't reach {server || "the server"}. Downloaded chapters still work.</span>
          <button onClick={retry} className="shrink-0 underline">
            Try again
          </button>
        </div>
      )}
      {/* Keeps the content centered inside the banner's clear middle */}
      <main className="flex-1" style={scene ? { paddingLeft: scene.inset, paddingRight: scene.inset } : undefined}>
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
