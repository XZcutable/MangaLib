import { useEffect, useState } from "react"
import { Navigate, useLocation } from "react-router"
import { BookOpen, Moon, Server, Sun } from "lucide-react"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { isNative } from "../lib/storage"

// Server address (mobile app), login and registration
export function Connect() {
  const auth = useAuth()
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const dark = theme === "dark"

  const [editingServer, setEditingServer] = useState(false)
  const [serverInput, setServerInput] = useState(auth.server)
  const [mode, setMode] = useState("login")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const info = auth.serverInfo
  const askServer = auth.status === "needs-server" || editingServer

  useEffect(() => {
    if (info?.needs_setup) setMode("register")
  }, [info?.needs_setup])

  if (auth.status === "ready") {
    return <Navigate to={location.state?.from ?? "/"} replace />
  }

  const run = async (action) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await action()
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  const submitServer = (event) => {
    event.preventDefault()
    run(async () => {
      await auth.connect(serverInput)
      setEditingServer(false)
    })
  }

  const submitAccount = (event) => {
    event.preventDefault()
    run(async () => {
      if (mode === "register") {
        const { user } = await auth.register(username, password)
        if (!user.approved) {
          setMode("login")
          setNotice("Account created. An admin needs to approve it before you can log in.")
          return
        }
      }
      await auth.login(username, password)
    })
  }

  const input = `w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent ${
    dark
      ? "bg-gray-800 border-gray-700 text-white placeholder-gray-500"
      : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"
  }`
  const label = `block text-sm mb-1 ${dark ? "text-gray-300" : "text-gray-700"}`
  const muted = dark ? "text-gray-400" : "text-gray-600"
  const canRegister = info?.registration_open

  return (
    <div
      className={`min-h-screen flex items-center justify-center px-4 py-10 ${dark ? "bg-gray-950" : "bg-gray-50"}`}
    >
      <div
        className={`w-full max-w-sm rounded-lg border p-6 sm:p-8 ${
          dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
        }`}
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-blue-500" />
            <span className={`font-semibold ${dark ? "text-white" : "text-gray-900"}`}>myMangaLib</span>
          </div>
          <button
            onClick={toggleTheme}
            className={`p-2 rounded-md ${dark ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-100 text-gray-700"}`}
            aria-label="Toggle theme"
          >
            {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>

        {auth.status === "loading" ? (
          <p className={muted}>Connecting…</p>
        ) : auth.status === "offline" && !askServer ? (
          <div className="space-y-4">
            <p className={muted}>Can't reach {auth.server || "the server"}. Check it's running and that you're on the right network.</p>
            <button onClick={auth.retry} className="w-full py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              Try again
            </button>
            <button onClick={() => setEditingServer(true)} className="w-full py-2 text-blue-500 text-sm">
              Use a different server
            </button>
          </div>
        ) : askServer ? (
          <form onSubmit={submitServer} className="space-y-4">
            <div>
              <h1 className={`text-xl mb-1 ${dark ? "text-white" : "text-gray-900"}`}>Connect to your server</h1>
              <p className={`text-sm ${muted}`}>The address you use to open myMangaLib in a browser.</p>
            </div>
            <div>
              <label htmlFor="server" className={label}>Server address</label>
              <input
                id="server"
                className={input}
                value={serverInput}
                onChange={(event) => setServerInput(event.target.value)}
                placeholder="192.168.1.20:5000 or https://manga.example.com"
                autoCapitalize="none"
                autoCorrect="off"
                inputMode="url"
                required={isNative}
                autoFocus
              />
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button disabled={busy} className="w-full py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-60">
              {busy ? "Checking…" : "Connect"}
            </button>
            {editingServer && (
              <button type="button" onClick={() => setEditingServer(false)} className="w-full py-2 text-sm text-blue-500">
                Cancel
              </button>
            )}
          </form>
        ) : (
          <form onSubmit={submitAccount} className="space-y-4">
            <div>
              <h1 className={`text-xl mb-1 ${dark ? "text-white" : "text-gray-900"}`}>
                {info?.needs_setup ? "Create the owner account" : mode === "register" ? "Create an account" : "Log in"}
              </h1>
              {info?.needs_setup && (
                <p className={`text-sm ${muted}`}>This is a new server. The first account manages it.</p>
              )}
            </div>
            <div>
              <label htmlFor="username" className={label}>Username</label>
              <input
                id="username"
                className={input}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                required
                autoFocus
              />
            </div>
            <div>
              <label htmlFor="password" className={label}>Password</label>
              <input
                id="password"
                type="password"
                className={input}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={mode === "register" ? "new-password" : "current-password"}
                required
              />
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            {notice && <p className="text-sm text-green-500">{notice}</p>}
            <button disabled={busy} className="w-full py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-60">
              {busy ? "Please wait…" : mode === "register" ? "Create account" : "Log in"}
            </button>
            {canRegister && !info?.needs_setup && (
              <button
                type="button"
                onClick={() => setMode(mode === "register" ? "login" : "register")}
                className="w-full text-sm text-blue-500"
              >
                {mode === "register" ? "I already have an account" : "Create an account"}
              </button>
            )}
          </form>
        )}

        {!askServer && auth.status !== "loading" && (isNative || auth.server) && (
          <button
            onClick={() => {
              setServerInput(auth.server)
              setEditingServer(true)
            }}
            className={`mt-6 w-full flex items-center justify-center gap-2 text-xs ${muted}`}
          >
            <Server className="w-3.5 h-3.5" />
            {auth.server || "This site"} · change
          </button>
        )}
      </div>
    </div>
  )
}
