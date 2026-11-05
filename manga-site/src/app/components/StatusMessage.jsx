import { useTheme } from "../context/ThemeContext"
import { Tenma } from "./Tenma"

// A message card for empty lists and errors. `pose` adds a small Tenma above the message.
export function StatusMessage({ message, onRetry, children, pose }) {
  const { theme } = useTheme()
  return (
    <div
      className={`rounded-lg border p-6 text-center ${
        theme === "dark"
          ? "bg-gray-900 border-gray-800 text-gray-400"
          : "bg-white border-gray-200 text-gray-600"
      }`}
    >
      {pose && <Tenma pose={pose} size="h-52 sm:h-64" className="mx-auto mb-4" />}
      <p>{message}</p>
      {children}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-brand-600 text-white rounded-md hover:bg-brand-700 transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  )
}
