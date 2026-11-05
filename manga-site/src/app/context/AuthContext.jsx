import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"
import { api, ApiError, configure, normalizeServerUrl } from "../lib/api"
import { getItem, setItem, isNative } from "../lib/storage"

// The default site name (the <title> in index.html)
const DEFAULT_SITE_NAME = "myMangaLib"

// The server in use and its token. Kept beside SERVERS_KEY so an older app version still finds its login.
const SERVER_KEY = "server"
const TOKEN_KEY = "token"
// Saved servers, most recently used first: [{ url, token, username, siteName }].
// url "" is the site the web app was opened from.
const SERVERS_KEY = "servers"

async function loadServers() {
  try {
    const list = JSON.parse((await getItem(SERVERS_KEY)) ?? "null")
    if (Array.isArray(list)) return list.filter((entry) => typeof entry?.url === "string")
  } catch {
    // Unreadable list: start again from the current server below
  }
  // Before saved servers existed there was one server and one token
  const url = await getItem(SERVER_KEY)
  if (url === null && isNative) return []
  return [{ url: url ?? "", token: await getItem(TOKEN_KEY), username: null, siteName: null }]
}

const AuthContext = createContext(undefined)

// status:
//   "loading"      reading saved login
//   "needs-server" the app has no server yet (mobile only; the web build uses its own origin)
//   "logged-out"   server known, no valid token
//   "offline"      saved login exists but the server can't be reached
//   "ready"        logged in
export function AuthProvider({ children }) {
  const [status, setStatus] = useState("loading")
  const [server, setServerState] = useState("")
  const [serverInfo, setServerInfo] = useState(null)
  const [user, setUser] = useState(null)
  const [servers, setServers] = useState([])
  // True after the user logs out themselves. The login screen then starts fresh at home
  // instead of returning to the page they logged out from.
  const [loggedOutOnPurpose, setLoggedOutOnPurpose] = useState(false)

  const serversRef = useRef([])
  const serverRef = useRef("")
  // Goes up on every restore, so answers from the server used before a switch are dropped
  const generation = useRef(0)

  // Changes the saved entry for `url` (adding it if missing) and stores the list
  const updateServer = useCallback(async (url, changes, { moveToTop = false } = {}) => {
    const list = serversRef.current
    const existing = list.find((entry) => entry.url === url)
    const entry = { url, token: null, username: null, siteName: null, ...existing, ...changes }
    const others = list.filter((item) => item.url !== url)
    const next = moveToTop || !existing ? [entry, ...others] : list.map((item) => (item.url === url ? entry : item))
    serversRef.current = next
    setServers(next)
    await setItem(SERVERS_KEY, JSON.stringify(next))
  }, [])

  const removeServer = useCallback(async (url) => {
    const next = serversRef.current.filter((entry) => entry.url !== url)
    serversRef.current = next
    setServers(next)
    await setItem(SERVERS_KEY, JSON.stringify(next))
  }, [])

  const clearToken = useCallback(async () => {
    configure({ token: null })
    setUser(null)
    await setItem(TOKEN_KEY, null)
    if (serversRef.current.some((entry) => entry.url === serverRef.current)) {
      await updateServer(serverRef.current, { token: null })
    }
  }, [updateServer])

  const restore = useCallback(async () => {
    const run = ++generation.current
    const current = () => run === generation.current
    setStatus("loading")
    const list = await loadServers()
    serversRef.current = list
    setServers(list)
    const savedServer = (await getItem(SERVER_KEY)) ?? list[0]?.url ?? ""
    const entry = list.find((item) => item.url === savedServer)
    const savedToken = entry ? entry.token : await getItem(TOKEN_KEY)
    if (!current()) return
    configure({ server: savedServer, token: savedToken })
    serverRef.current = savedServer
    setServerState(savedServer)

    if (!savedServer && isNative) {
      setStatus("needs-server")
      return
    }
    if (!entry) await updateServer(savedServer, { token: savedToken })

    api
      .serverInfo()
      .then((info) => current() && setServerInfo(info))
      .catch(() => {})

    if (!savedToken) {
      setStatus("logged-out")
      return
    }
    try {
      const { user } = await api.me()
      if (!current()) return
      setUser(user)
      setStatus("ready")
    } catch (error) {
      if (!current()) return
      if (error instanceof ApiError && error.status === 401) {
        await clearToken()
        setStatus("logged-out")
      } else {
        setStatus("offline")
      }
    }
  }, [clearToken, updateServer])

  useEffect(() => {
    configure({
      onUnauthorized: () => {
        // The token was revoked or expired while using the app
        clearToken().then(() => setStatus("logged-out"))
      },
      // Shows the "choose a new username" screen (RequireAuth) without waiting for the next refresh
      onUsernameChangeRequired: () => setUser((current) => current && { ...current, must_change_username: true }),
    })
    restore()
  }, [restore, clearToken])

  // The list shows each server's name and who is logged in there
  useEffect(() => {
    const entry = servers.find((item) => item.url === server)
    if (!entry) return
    const changes = {}
    if (serverInfo?.site_name && serverInfo.site_name !== entry.siteName) changes.siteName = serverInfo.site_name
    if (user?.username && user.username !== entry.username) changes.username = user.username
    if (Object.keys(changes).length) updateServer(server, changes)
  }, [servers, server, serverInfo?.site_name, user?.username, updateServer])

  // Uses a saved server and its login (if it still has one)
  const switchServer = useCallback(
    async (url) => {
      generation.current++
      setStatus("loading")
      const entry = serversRef.current.find((item) => item.url === url)
      configure({ token: null })
      setUser(null)
      setServerInfo(null)
      // Without a login there's no page to come back to on this server
      setLoggedOutOnPurpose(!entry?.token)
      await updateServer(url, {}, { moveToTop: true })
      await setItem(SERVER_KEY, url)
      await setItem(TOKEN_KEY, entry?.token ?? null)
      await restore()
    },
    [restore, updateServer],
  )

  // Checks the address points at a myMangaLib server, then saves it (or switches to it if it's saved)
  const connect = useCallback(
    async (input) => {
      const url = normalizeServerUrl(input)
      const info = await api.serverInfo(url)
      if (info?.name !== "myMangaLib") {
        throw new ApiError(0, "not_mangalib", "That address isn't a myMangaLib server")
      }
      if (serversRef.current.some((entry) => entry.url === url && entry.token)) {
        await switchServer(url)
        return info
      }
      generation.current++
      configure({ server: url, token: null })
      setUser(null)
      serverRef.current = url
      await updateServer(url, { siteName: info.site_name ?? null }, { moveToTop: true })
      await setItem(SERVER_KEY, url)
      await setItem(TOKEN_KEY, null)
      setServerState(url)
      setServerInfo(info)
      setLoggedOutOnPurpose(true)
      setStatus("logged-out")
      return info
    },
    [switchServer, updateServer],
  )

  const login = useCallback(
    async (username, password) => {
      const device = isNative ? "myMangaLib app" : navigator.userAgent.slice(0, 100)
      const result = await api.login(username, password, device)
      configure({ token: result.token })
      await setItem(TOKEN_KEY, result.token)
      await updateServer(serverRef.current, { token: result.token, username: result.user.username })
      setUser(result.user)
      setLoggedOutOnPurpose(false)
      setStatus("ready")
    },
    [updateServer],
  )

  const register = useCallback(async (username, password) => {
    const result = await api.register(username, password)
    // The first account turns off "needs setup"
    api.serverInfo().then(setServerInfo).catch(() => {})
    return result
  }, [])

  // Logs out of the current server. It stays in the saved list.
  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      // Already invalid or offline. Forget it locally either way.
    }
    await clearToken()
    setLoggedOutOnPurpose(true)
    setStatus("logged-out")
  }, [clearToken])

  // Removes a saved server and logs out of it. Removing the current one moves to the next saved
  // server, or back to the address screen.
  const forgetServer = useCallback(
    async (url) => {
      const entry = serversRef.current.find((item) => item.url === url)
      if (entry?.token) api.logoutFrom(url, entry.token).catch(() => {})
      await removeServer(url)
      if (url !== serverRef.current) return
      const next = serversRef.current[0]
      if (next) {
        await switchServer(next.url)
        return
      }
      generation.current++
      configure({ server: "", token: null })
      serverRef.current = ""
      setUser(null)
      setServerInfo(null)
      setServerState("")
      await setItem(SERVER_KEY, null)
      await setItem(TOKEN_KEY, null)
      setLoggedOutOnPurpose(true)
      if (isNative) setStatus("needs-server")
      else await restore()
    },
    [removeServer, switchServer, restore],
  )

  // Updates the account, including the admin's count of sign-ups waiting for approval
  const refreshUser = useCallback(async () => {
    try {
      const { user } = await api.me()
      setUser(user)
    } catch {
      // Offline or logged out; the request handler deals with 401
    }
  }, [])

  // Admins see new sign-ups while the app is open and when they come back to it
  useEffect(() => {
    if (status !== "ready" || !user?.is_admin) return
    const refresh = () => document.visibilityState === "visible" && refreshUser()
    const timer = setInterval(refresh, 30_000)
    document.addEventListener("visibilitychange", refresh)
    return () => {
      clearInterval(timer)
      document.removeEventListener("visibilitychange", refresh)
    }
  }, [status, user?.is_admin, refreshUser])

  // The owner can rename the site in Settings. Until the server answers, the name the page was built with.
  const siteName = serverInfo?.site_name || DEFAULT_SITE_NAME
  useEffect(() => {
    document.title = siteName
  }, [siteName])

  const refreshServerInfo = useCallback(
    () => api.serverInfo().then((info) => (setServerInfo(info), info)),
    [],
  )

  return (
    <AuthContext.Provider
      value={{
        status,
        loggedOutOnPurpose,
        server,
        serverInfo,
        siteName,
        user,
        servers,
        connect,
        login,
        register,
        logout,
        switchServer,
        forgetServer,
        setUser,
        refreshUser,
        retry: restore,
        refreshServerInfo,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// How a saved server is shown: its site name, or its address
export function serverAddress(url) {
  return url || window.location.origin
}

export function serverLabel(entry) {
  if (entry.siteName) return entry.siteName
  return serverAddress(entry.url).replace(/^https?:\/\//, "")
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
