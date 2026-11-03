import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { api } from "../lib/api"
import { getLocal, setLocal, isNative } from "../lib/storage"

const formatDate = (value) => (value ? new Date(value).toLocaleString() : "never")

export function Settings() {
  const { theme, toggleTheme } = useTheme()
  const { user, server, serverInfo, logout, changeServer } = useAuth()
  const navigate = useNavigate()
  const dark = theme === "dark"
  const [devices, setDevices] = useState(null)
  const [rightToLeft, setRightToLeft] = useState(() => getLocal("readerDirection", "ltr") === "rtl")

  const loadDevices = useCallback(() => {
    api
      .tokens()
      .then(({ tokens }) => setDevices(tokens))
      .catch((error) => toast.error(error.message))
  }, [])
  useEffect(loadDevices, [loadDevices])

  const revoke = async (id) => {
    try {
      await api.revokeToken(id)
      loadDevices()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const card = `rounded-lg border p-6 mb-6 ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`
  const heading = `mb-4 ${dark ? "text-white" : "text-gray-900"}`
  const muted = dark ? "text-gray-400" : "text-gray-600"
  const text = dark ? "text-gray-200" : "text-gray-800"
  const button = `px-4 py-2 rounded-md border transition-colors ${
    dark
      ? "border-gray-700 text-gray-200 hover:bg-gray-800"
      : "border-gray-300 text-gray-800 hover:bg-gray-100"
  }`

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className={`mb-6 ${dark ? "text-white" : "text-gray-900"}`}>Settings</h1>

      <section className={card}>
        <h2 className={heading}>Account</h2>
        <p className={text}>{user?.username}</p>
        <p className={`text-sm mb-4 ${muted}`}>Role: {user?.role}</p>
        <div className="flex flex-wrap gap-3">
          <button className={button} onClick={() => logout().then(() => navigate("/connect"))}>
            Log out
          </button>
          {(isNative || server) && (
            <button
              className={button}
              onClick={() => changeServer().then(() => navigate("/connect"))}
            >
              Change server
            </button>
          )}
        </div>
        <p className={`text-sm mt-4 ${muted}`}>
          Server: {server || window.location.origin}
          {serverInfo?.version && ` (myMangaLib ${serverInfo.version})`}
        </p>
        {user?.is_owner && (
          <p className={`text-sm mt-1 ${muted}`}>
            Library folders and scanning are still managed in the classic web interface, under
            Settings.
          </p>
        )}
      </section>

      <section className={card}>
        <h2 className={heading}>Reading</h2>
        <div className="flex flex-wrap gap-3">
          <button className={button} onClick={toggleTheme}>
            Theme: {dark ? "Dark" : "Light"}
          </button>
          <button
            className={button}
            onClick={() => {
              setLocal("readerDirection", rightToLeft ? "ltr" : "rtl")
              setRightToLeft(!rightToLeft)
            }}
          >
            Page direction: {rightToLeft ? "Right to left (manga)" : "Left to right"}
          </button>
        </div>
      </section>

      <section className={card}>
        <h2 className={heading}>Signed-in devices</h2>
        {devices === null ? (
          <p className={muted}>Loading…</p>
        ) : (
          <ul className={`divide-y ${dark ? "divide-gray-800" : "divide-gray-200"}`}>
            {devices.map((device) => (
              <li key={device.id} className="flex items-center justify-between gap-4 py-3">
                <div className="min-w-0">
                  <p className={`truncate ${text}`}>
                    {device.name || "Unknown device"}
                    {device.current && (
                      <span className="ml-2 text-xs text-blue-500">This device</span>
                    )}
                  </p>
                  <p className={`text-xs ${muted}`}>Last used {formatDate(device.last_used)}</p>
                </div>
                {!device.current && (
                  <button
                    className="text-sm text-red-500 hover:text-red-400 shrink-0"
                    onClick={() => revoke(device.id)}
                  >
                    Sign out
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
