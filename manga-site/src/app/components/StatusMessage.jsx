import { useTheme } from "../context/ThemeContext"

export function StatusMessage({ message, onRetry, children }) {
  const { theme } = useTheme()
  return (
    <div
      className={`rounded-lg border p-6 text-center ${
        theme === "dark"
          ? "bg-gray-900 border-gray-800 text-gray-400"
          : "bg-white border-gray-200 text-gray-600"
      }`}
    >
      <p>{message}</p>
      {children}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  )
}
