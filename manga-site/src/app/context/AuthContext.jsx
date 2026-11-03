import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api, ApiError, configure, normalizeServerUrl } from "../lib/api"
import { getItem, setItem, isNative } from "../lib/storage"

const SERVER_KEY = "server"
const TOKEN_KEY = "token"

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
  // True after the user logs out themselves. The login screen then starts fresh at home
  // instead of returning to the page they logged out from.
  const [loggedOutOnPurpose, setLoggedOutOnPurpose] = useState(false)

  const clearToken = useCallback(async () => {
    configure({ token: null })
    setUser(null)
    await setItem(TOKEN_KEY, null)
  }, [])

  const restore = useCallback(async () => {
    setStatus("loading")
    const savedServer = (await getItem(SERVER_KEY)) ?? ""
    const savedToken = await getItem(TOKEN_KEY)
    configure({ server: savedServer, token: savedToken })
    setServerState(savedServer)

    if (!savedServer && isNative) {
      setStatus("needs-server")
      return
    }

    api.serverInfo().then(setServerInfo).catch(() => {})

    if (!savedToken) {
      setStatus("logged-out")
      return
    }
    try {
      const { user } = await api.me()
      setUser(user)
      setStatus("ready")
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await clearToken()
        setStatus("logged-out")
      } else {
        setStatus("offline")
      }
    }
  }, [clearToken])

  useEffect(() => {
    configure({
      onUnauthorized: () => {
        // The token was revoked or expired while using the app
        clearToken().then(() => setStatus("logged-out"))
      },
    })
    restore()
  }, [restore, clearToken])

  // Checks the address points at a myMangaLib server before saving it
  const connect = useCallback(
    async (input) => {
      const url = normalizeServerUrl(input)
      const info = await api.serverInfo(url)
      if (info?.name !== "myMangaLib") {
        throw new ApiError(0, "not_mangalib", "That address isn't a myMangaLib server")
      }
      await clearToken()
      await setItem(SERVER_KEY, url || null)
      configure({ server: url })
      setServerState(url)
      setServerInfo(info)
      setStatus("logged-out")
      return info
    },
    [clearToken],
  )

  const login = useCallback(async (username, password) => {
    const device = isNative ? "myMangaLib app" : navigator.userAgent.slice(0, 100)
    const result = await api.login(username, password, device)
    configure({ token: result.token })
    await setItem(TOKEN_KEY, result.token)
    setUser(result.user)
    setLoggedOutOnPurpose(false)
    setStatus("ready")
  }, [])

  const register = useCallback(async (username, password) => {
    const result = await api.register(username, password)
    // The first account turns off "needs setup"
    api.serverInfo().then(setServerInfo).catch(() => {})
    return result
  }, [])

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

  // Back to the server address screen. On the web this clears a custom server.
  const changeServer = useCallback(async () => {
    await logout()
    await setItem(SERVER_KEY, null)
    configure({ server: "" })
    setServerState("")
    setServerInfo(null)
    setStatus(isNative ? "needs-server" : "logged-out")
  }, [logout])

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
        user,
        connect,
        login,
        register,
        logout,
        changeServer,
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

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
