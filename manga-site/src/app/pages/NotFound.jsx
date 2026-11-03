import { Link } from "react-router"
import { useTheme } from "../context/ThemeContext"
export function NotFound() {
  const { theme } = useTheme()
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
      <h1
        className={`mb-4 ${theme === "dark" ? "text-white" : "text-gray-900"}`}
      >
        404 - Page Not Found
      </h1>
      <p
        className={`mb-6 ${
          theme === "dark" ? "text-gray-400" : "text-gray-600"
        }`}
      >
        The page you're looking for doesn't exist.
      </p>
      <Link
        to="/"
        className="inline-block px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
      >
        Back to Home
      </Link>
    </div>
  )
}
