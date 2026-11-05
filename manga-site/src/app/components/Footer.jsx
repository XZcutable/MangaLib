import { Link } from "react-router"
import { Github } from "lucide-react"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { APP_VERSION, GITHUB_PAGE } from "../lib/version"

export function Footer() {
  const { theme } = useTheme()
  const { siteName, serverInfo } = useAuth()
  const muted = theme === "dark" ? "text-gray-400 hover:text-white" : "text-gray-600 hover:text-gray-900"
  // The phone app can be older or newer than the server it talks to
  const serverVersion = serverInfo?.version
  const versions =
    serverVersion && serverVersion !== APP_VERSION ? `v${APP_VERSION} · server v${serverVersion}` : `v${APP_VERSION}`

  return (
    <footer
      className={`${
        theme === "dark"
          ? "bg-gray-900 border-gray-800"
          : "bg-gray-100 border-gray-200"
      } border-t mt-auto`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span
              className={`font-semibold ${
                theme === "dark" ? "text-white" : "text-gray-900"
              }`}
            >
              {siteName}
            </span>
            <Link to="/about" className={`transition-colors ${muted}`}>
              {versions}
            </Link>
          </div>

          <div className="flex items-center gap-4">
            <Link to="/about" className={`transition-colors ${muted}`}>
              About
            </Link>
            <a
              href={GITHUB_PAGE}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex items-center gap-2 transition-colors ${muted}`}
            >
              <Github className="w-5 h-5" />
              <span>View on GitHub</span>
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}
