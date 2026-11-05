import { useEffect, useState } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router"
import { BookOpen, ChevronRight, Moon, Server, Sun } from "lucide-react"
import { serverAddress, serverLabel, useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { useDownloads } from "../context/DownloadsContext"
import { isNative } from "../lib/storage"
import { normalizeServerUrl } from "../lib/api"
import { Tenma } from "../components/Tenma"

// Server address (mobile app), login and registration.
// Opened with state { addServer: true } (from Settings) it asks for another server while logged in.
export function Connect() {
  const auth = useAuth()
  const downloads = useDownloads()
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()
  const dark = theme === "dark"

  const addingServer = Boolean(location.state?.addServer)
  const [editingServer, setEditingServer] = useState(addingServer)
  const [serverInput, setServerInput] = useState(addingServer ? "" : auth.server)
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

  if (auth.status === "ready" && !editingServer) {
    // Never send someone back to the log-out page, which would log them out again
    const from = location.state?.from
    const target = from && !from.startsWith("/logout") && !from.startsWith("/connect") ? from : "/"
    return <Navigate to={target} replace />
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

  // A page saved from one server means nothing on another, so drop it before changing server
  const forgetFrom = () => navigate("/connect", { replace: true, state: null })

  const submitServer = (event) => {
    event.preventDefault()
    run(async () => {
      const url = normalizeServerUrl(serverInput)
      if (url !== auth.server) forgetFrom()
      await auth.connect(serverInput)
      setEditingServer(false)
    })
  }

  const pickServer = (url) => {
    if (url === auth.server && auth.status === "logged-out") {
      setEditingServer(false)
      return
    }
    forgetFrom()
    setEditingServer(false)
    run(() => auth.switchServer(url))
  }

  const cancelEditing = () => {
    if (auth.status === "ready") navigate(-1)
    else setEditingServer(false)
  }

  // Other saved servers, to switch to with one tap
  const savedServers = auth.servers.filter(
    (entry) => !(entry.url === auth.server && (auth.status === "needs-server" || auth.status === "ready")),
  )

  const submitAccount = (event) => {
    event.preventDefault()
    // Spaces around the name are easy to type by accident (or added by autocomplete)
    const name = username.trim()
    setUsername(name)
    run(async () => {
      if (mode === "register") {
        const { user } = await auth.register(name, password)
        if (!user.approved) {
          setMode("login")
          setNotice("Account created. An admin needs to approve it before you can log in.")
          return
        }
      }
      await auth.login(name, password)
    })
  }

  const input = `w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent ${
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
      {/* The form stays centered. Tenma greets people: small above it on phones; on wider screens she
          stands to its left, outside the layout, so she doesn't push the form off center. */}
      <div className="relative w-full max-w-sm flex flex-col items-center">
        <Tenma
          pose={auth.status === "offline" && !askServer ? "sleeping" : "wave"}
          size="h-52 lg:h-[22rem] xl:h-[28rem]"
          className="mb-2 lg:mb-0 lg:absolute lg:right-full lg:mr-10 lg:top-1/2 lg:-translate-y-1/2"
        />
        <div
          className={`w-full rounded-lg border p-6 sm:p-8 ${
            dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          }`}
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-brand-500" />
              <span className={`font-semibold ${dark ? "text-white" : "text-gray-900"}`}>{auth.siteName}</span>
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
              <button onClick={auth.retry} className="w-full py-2 bg-brand-600 text-white rounded-md hover:bg-brand-700">
                Try again
              </button>
              {downloads.hasDownloads && (
                <Link
                  to="/downloads"
                  className={`block w-full py-2 text-center rounded-md border ${
                    dark ? "border-gray-700 text-gray-200" : "border-gray-300 text-gray-800"
                  }`}
                >
                  Read downloaded chapters
                </Link>
              )}
              <button onClick={() => setEditingServer(true)} className="w-full py-2 text-brand-500 text-sm">
                Use a different server
              </button>
            </div>
          ) : askServer ? (
            <form onSubmit={submitServer} className="space-y-4">
              <div>
                {savedServers.length > 0 && (
                  <>
                    <h1 className={`text-xl mb-3 ${dark ? "text-white" : "text-gray-900"}`}>Your servers</h1>
                    <ul className={`mb-6 rounded-md border divide-y ${dark ? "border-gray-700 divide-gray-700" : "border-gray-200 divide-gray-200"}`}>
                      {savedServers.map((entry) => (
                        <li key={entry.url}>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => pickServer(entry.url)}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 text-left disabled:opacity-60 ${
                              dark ? "hover:bg-gray-800" : "hover:bg-gray-50"
                            }`}
                          >
                            <Server className="w-4 h-4 shrink-0 text-brand-500" />
                            <span className="min-w-0 flex-1">
                              <span className={`block truncate ${dark ? "text-white" : "text-gray-900"}`}>{serverLabel(entry)}</span>
                              <span className={`block truncate text-xs ${muted}`}>
                                {entry.token && entry.username ? `${entry.username} · ` : entry.token ? "" : "Not logged in · "}
                                {serverAddress(entry.url)}
                              </span>
                            </span>
                            <ChevronRight className={`w-4 h-4 shrink-0 ${muted}`} />
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                <h1 className={`text-xl mb-1 ${dark ? "text-white" : "text-gray-900"}`}>
                  {savedServers.length > 0 || addingServer ? "Add a server" : "Connect to your server"}
                </h1>
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
                  autoFocus={savedServers.length === 0}
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <button disabled={busy} className="w-full py-2 bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-60">
                {busy ? "Checking…" : "Connect"}
              </button>
              {editingServer && (
                <button type="button" onClick={cancelEditing} className="w-full py-2 text-sm text-brand-500">
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
              <button disabled={busy} className="w-full py-2 bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-60">
                {busy ? "Please wait…" : mode === "register" ? "Create account" : "Log in"}
              </button>
              {canRegister && !info?.needs_setup && (
                <button
                  type="button"
                  onClick={() => setMode(mode === "register" ? "login" : "register")}
                  className="w-full text-sm text-brand-500"
                >
                  {mode === "register" ? "I already have an account" : "Create an account"}
                </button>
              )}
            </form>
          )}

          {!askServer && auth.status !== "loading" && (isNative || auth.server) && (
            <button
              onClick={() => {
                // With several saved servers the current one is in the list, so the box is for a new one
                setServerInput(auth.servers.length > 1 ? "" : auth.server)
                setEditingServer(true)
              }}
              className={`mt-6 w-full flex items-center justify-center gap-2 text-xs ${muted}`}
            >
              <Server className="w-3.5 h-3.5" />
              {auth.server || "This site"} · {auth.servers.length > 1 ? "switch" : "change"}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
