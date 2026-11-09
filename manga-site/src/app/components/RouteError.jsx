import { useEffect } from "react"
import { Link, useLocation, useRouteError } from "react-router"
import { useTheme } from "../context/ThemeContext"
import { addLog } from "../lib/logBuffer"
import { Tenma } from "./Tenma"

// Shown instead of a blank page when a page crashes. The error goes into the app log, so a bug
// report sent from here includes it.
export function RouteError() {
  const error = useRouteError()
  const location = useLocation()
  const { theme } = useTheme()
  const dark = theme === "dark"

  useEffect(() => {
    addLog("error", `Page crashed at ${location.pathname}:`, error)
  }, [error, location.pathname])

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md text-center">
        <Tenma className="mx-auto mb-4" />
        <h1 className={`mb-2 ${dark ? "text-white" : "text-gray-900"}`}>Something went wrong</h1>
        <p className={`mb-6 ${dark ? "text-gray-400" : "text-gray-600"}`}>
          This page ran into a problem. Reloading usually helps. If it keeps happening, please report it.
        </p>
        <div className="flex flex-wrap gap-3 justify-center">
          <button
            className="px-4 py-2 rounded-md bg-brand-600 text-white hover:bg-brand-700"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
          <Link
            to="/feedback?kind=bug"
            state={{ from: location.pathname }}
            className={`px-4 py-2 rounded-md border ${dark ? "border-gray-700 text-gray-200" : "border-gray-300 text-gray-800"}`}
          >
            Report this bug
          </Link>
        </div>
      </div>
    </div>
  )
}
