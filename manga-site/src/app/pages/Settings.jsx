import { useCallback, useEffect, useState } from "react"
import { useLocation, useNavigate } from "react-router"
import { toast } from "sonner"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { useStyles } from "../hooks/useStyles"
import { api, parseServerDate } from "../lib/api"
import { getLocal, setLocal, isNative } from "../lib/storage"
import { AccountSection } from "../components/settings/AccountSection"
import { LibrarySection } from "../components/settings/LibrarySection"
import { TagsSection } from "../components/settings/TagsSection"
import { UsersSection } from "../components/settings/UsersSection"
import { SettingSwitch } from "../components/settings/SettingSwitch"
import { UpdatesSection } from "../components/settings/UpdatesSection"
import { canSelfUpdate } from "../lib/updater"

const formatDate = (value) => (value ? parseServerDate(value).toLocaleString() : "never")

export function Settings() {
  const { toggleTheme } = useTheme()
  const { user, server, serverInfo, logout, changeServer } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const s = useStyles()

  // Links like /settings#users (from the "waiting" badge) open at that section
  useEffect(() => {
    if (!location.hash) return
    const timer = setTimeout(() => {
      document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: "smooth" })
    }, 100)
    return () => clearTimeout(timer)
  }, [location.hash])
  const [devices, setDevices] = useState(null)
  const [rightToLeft, setRightToLeft] = useState(() => getLocal("readerDirection", "ltr") === "rtl")
  const [alwaysShowControls, setAlwaysShowControls] = useState(
    () => getLocal("readerControls", "tap") === "always",
  )

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

  const sections = [
    { id: "account", label: "Account" },
    { id: "reading", label: "Reading" },
    ...(user?.is_owner ? [{ id: "library", label: "Library" }] : []),
    ...(user?.is_admin
      ? [
          { id: "users", label: user.pending_users ? `Users (${user.pending_users} waiting)` : "Users" },
          { id: "tags", label: "Tags" },
        ]
      : []),
    ...(canSelfUpdate ? [{ id: "updates", label: "Updates" }] : []),
    { id: "devices", label: "Devices" },
  ]

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className={`mb-4 ${s.dark ? "text-white" : "text-gray-900"}`}>Settings</h1>
      {sections.length > 3 && (
        <nav className="flex flex-wrap gap-2 mb-6" aria-label="Settings sections">
          {sections.map((section) => (
            <a key={section.id} href={`#${section.id}`} className={s.chip(false)}>
              {section.label}
            </a>
          ))}
        </nav>
      )}

      <div id="account" className="scroll-mt-20">
        <AccountSection>
          <div className={`mt-8 pt-6 border-t ${s.divider}`}>
            <div className="flex flex-wrap gap-3">
              <button className={s.button} onClick={() => logout().then(() => navigate("/connect"))}>
                Log out
              </button>
              {(isNative || server) && (
                <button
                  className={s.button}
                  onClick={() => changeServer().then(() => navigate("/connect"))}
                >
                  Change server
                </button>
              )}
            </div>
            <p className={`text-sm mt-4 ${s.muted}`}>
              Server: {server || window.location.origin}
              {serverInfo?.version && ` (myMangaLib ${serverInfo.version})`}
            </p>
            {serverInfo?.classic_ui_path && (
              <a
                href={`${server}${serverInfo.classic_ui_path}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-2 text-sm text-blue-500 hover:text-blue-400"
              >
                Open the classic web interface
              </a>
            )}
          </div>
        </AccountSection>
      </div>

      <section id="reading" className={`${s.card} scroll-mt-20`}>
        <h2 className={s.heading}>Reading</h2>
        <div className={`divide-y ${s.divider}`}>
          <SettingSwitch
            label="Dark theme"
            description="Applies on this device."
            checked={s.dark}
            onChange={toggleTheme}
          />
          <SettingSwitch
            label="Read right to left"
            description="For Japanese manga: the next page is on the left, and swiping right turns forward."
            checked={rightToLeft}
            onChange={(value) => {
              setLocal("readerDirection", value ? "rtl" : "ltr")
              setRightToLeft(value)
            }}
          />
          <SettingSwitch
            label="Always show reader controls"
            description="Keeps the page picker and buttons on screen. When off, tap the middle of a page to show them."
            checked={alwaysShowControls}
            onChange={(value) => {
              setLocal("readerControls", value ? "always" : "tap")
              setAlwaysShowControls(value)
            }}
          />
        </div>
        <p className={`text-sm mt-3 ${s.muted}`}>
          In the reader, tap or click the left or right edge, swipe, or use the arrow keys to turn
          pages. The bottom bar jumps to any page or chapter.
        </p>
      </section>

      {user?.is_owner && (
        <div id="library" className="scroll-mt-20">
          <LibrarySection />
        </div>
      )}
      {user?.is_admin && (
        <>
          <div id="users" className="scroll-mt-20">
            <UsersSection />
          </div>
          <div id="tags" className="scroll-mt-20">
            <TagsSection />
          </div>
        </>
      )}

      {canSelfUpdate && (
        <div id="updates" className="scroll-mt-20">
          <UpdatesSection />
        </div>
      )}

      <section id="devices" className={`${s.card} scroll-mt-20`}>
        <h2 className={s.heading}>Signed-in devices</h2>
        {devices === null ? (
          <p className={s.muted}>Loading…</p>
        ) : (
          <ul className={`divide-y ${s.divider}`}>
            {devices.map((device) => (
              <li key={device.id} className="flex items-center justify-between gap-4 py-3">
                <div className="min-w-0">
                  <p className={`truncate ${s.text}`}>
                    {device.name || "Unknown device"}
                    {device.current && (
                      <span className="ml-2 text-xs text-blue-500">This device</span>
                    )}
                  </p>
                  <p className={`text-xs ${s.muted}`}>Last used {formatDate(device.last_used)}</p>
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
