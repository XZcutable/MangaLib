import { useState } from "react"
import { BookOpen, LogOut } from "lucide-react"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { api } from "../lib/api"

// Shown instead of the app when the account has to pick a new username: an admin asked for it,
// or the name breaks the username rules (e.g. spaces around it, from before they were checked).
export function ChooseUsername() {
  const { user, setUser, logout, siteName } = useAuth()
  const { theme } = useTheme()
  const dark = theme === "dark"

  const current = user?.username ?? ""
  const invalid = current !== current.trim()
  // A name with stray spaces only needs them removed, so offer the trimmed name
  const [username, setUsername] = useState(invalid ? current.trim() : "")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api.changeUsername(username.trim())
      setUser(result.user)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  const input = `w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent ${
    dark
      ? "bg-gray-800 border-gray-700 text-white placeholder-gray-500"
      : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"
  }`
  const muted = dark ? "text-gray-400" : "text-gray-600"

  return (
    <div className={`min-h-screen flex items-center justify-center px-4 py-10 ${dark ? "bg-gray-950" : "bg-gray-50"}`}>
      <div
        className={`w-full max-w-sm rounded-lg border p-6 sm:p-8 ${
          dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
        }`}
      >
        <div className="flex items-center gap-2 mb-6">
          <BookOpen className="w-6 h-6 text-brand-500" />
          <span className={`font-semibold ${dark ? "text-white" : "text-gray-900"}`}>{siteName}</span>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <h1 className={`text-xl mb-1 ${dark ? "text-white" : "text-gray-900"}`}>Choose a new username</h1>
            <p className={`text-sm ${muted}`}>
              {invalid
                ? "Your username starts or ends with a space, which isn't allowed anymore."
                : "An admin asked you to change your username."}{" "}
              Pick a new one to keep using your account. Your password and reading history stay the same.
            </p>
          </div>
          <div>
            <label htmlFor="new-username" className={`block text-sm mb-1 ${dark ? "text-gray-300" : "text-gray-700"}`}>
              New username
            </label>
            <input
              id="new-username"
              className={input}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              required
              autoFocus
            />
            <p className={`text-xs mt-1 ${muted}`}>Currently “{current}”</p>
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            disabled={busy || !username.trim()}
            className="w-full py-2 bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-60"
          >
            {busy ? "Saving…" : "Save username"}
          </button>
          <button
            type="button"
            onClick={logout}
            className={`w-full flex items-center justify-center gap-2 text-sm ${muted}`}
          >
            <LogOut className="w-4 h-4" />
            Log out
          </button>
        </form>
      </div>
    </div>
  )
}
