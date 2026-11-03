import { Github } from "lucide-react"
import { useTheme } from "../context/ThemeContext"
export function Footer() {
  const { theme } = useTheme()
  return (
    <footer
      className={`${
        theme === "dark"
          ? "bg-gray-900 border-gray-800"
          : "bg-gray-100 border-gray-200"
      } border-t mt-auto`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span
              className={`font-semibold ${
                theme === "dark" ? "text-white" : "text-gray-900"
              }`}
            >
              MangaReader
            </span>
            <span
              className={theme === "dark" ? "text-gray-500" : "text-gray-600"}
            >
              v1.0.0
            </span>
          </div>

          <div className="flex items-center gap-4">
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className={`flex items-center gap-2 transition-colors ${
                theme === "dark"
                  ? "text-gray-400 hover:text-white"
                  : "text-gray-600 hover:text-gray-900"
              }`}
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
