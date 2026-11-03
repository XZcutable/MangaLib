import { useTheme } from "../context/ThemeContext"

// Class names for the cards, inputs and buttons used across settings and management panels
export function useStyles() {
  const { theme } = useTheme()
  const dark = theme === "dark"
  return {
    dark,
    card: `rounded-lg border p-6 mb-6 ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`,
    heading: `mb-4 ${dark ? "text-white" : "text-gray-900"}`,
    subheading: `text-sm font-semibold mb-2 ${dark ? "text-gray-300" : "text-gray-700"}`,
    text: dark ? "text-gray-200" : "text-gray-800",
    muted: dark ? "text-gray-400" : "text-gray-600",
    divider: dark ? "divide-gray-800 border-gray-800" : "divide-gray-200 border-gray-200",
    input: `px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent ${
      dark
        ? "bg-gray-800 border-gray-700 text-white placeholder-gray-500"
        : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"
    }`,
    button: `px-4 py-2 rounded-md border transition-colors disabled:opacity-60 ${
      dark
        ? "border-gray-700 text-gray-200 hover:bg-gray-800"
        : "border-gray-300 text-gray-800 hover:bg-gray-100"
    }`,
    primaryButton:
      "px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-60",
    dangerButton:
      "px-4 py-2 rounded-md border border-red-600 text-red-500 hover:bg-red-600/10 transition-colors disabled:opacity-60",
    chip: (active) =>
      `text-sm px-3 py-1 rounded-full border transition-colors ${
        active
          ? "border-blue-600 bg-blue-600/15 text-blue-500"
          : dark
            ? "border-gray-700 text-gray-300 hover:bg-gray-800"
            : "border-gray-300 text-gray-700 hover:bg-gray-100"
      }`,
  }
}
