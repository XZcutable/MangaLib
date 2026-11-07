import { useCallback, useEffect, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router"
import { toast } from "sonner"
import { useAuth } from "../context/AuthContext"
import { ACCENTS, PAGE_BACKGROUNDS, useTheme } from "../context/ThemeContext"
import { useStyles } from "../hooks/useStyles"
import { api, parseServerDate, serverBase } from "../lib/api"
import { getLocal, setLocal, isNative } from "../lib/storage"
import { FIT_MODES, getFitMode, setFitMode } from "../lib/pageFit"
import { AccountSection } from "../components/settings/AccountSection"
import { LibrarySection } from "../components/settings/LibrarySection"
import { TagsSection } from "../components/settings/TagsSection"
import { UsersSection } from "../components/settings/UsersSection"
import { SuggestionsSection } from "../components/settings/SuggestionsSection"
import { SettingSwitch } from "../components/settings/SettingSwitch"
import { UpdatesSection } from "../components/settings/UpdatesSection"
import { ShareAppSection } from "../components/settings/ShareAppSection"
import { ServerUpdatesSection } from "../components/settings/ServerUpdatesSection"
import { ServersSection } from "../components/settings/ServersSection"
import { canSelfUpdate } from "../lib/updater"
import { canUseAppLock } from "../lib/appLock"
import { AppLockSection } from "../components/settings/AppLockSection"
import { useServerFeatures } from "../lib/features"

const formatDate = (value) => (value ? parseServerDate(value).toLocaleString() : "never")

export function Settings() {
  const { toggleTheme, accent, setAccent, pageBackground, setPageBackground } = useTheme()
  const { user, server, servers, serverInfo, logout } = useAuth()
  // On the web, only once a server other than this site has been added
  const showServers = isNative || servers.some((entry) => entry.url)
  const navigate = useNavigate()
  const location = useLocation()
  const s = useStyles()
  const features = useServerFeatures()

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
  const [fitMode, setFitModeState] = useState(getFitMode)

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
    ...(showServers ? [{ id: "servers", label: "Servers" }] : []),
    { id: "appearance", label: "Appearance" },
    { id: "reading", label: "Reading" },
    ...(canUseAppLock ? [{ id: "app-lock", label: "App lock" }] : []),
    ...(user?.is_owner ? [{ id: "library", label: "Library" }] : []),
    ...(user?.is_owner && features.serverUpdates
      ? [{
          id: "server-updates",
          label: user.server_update?.status === "ready" ? "Server update ready" : "Server updates",
        }]
      : []),
    ...(user?.is_admin
      ? [
          { id: "users", label: user.pending_users ? `Users (${user.pending_users} waiting)` : "Users" },
          ...(features.seriesDetails ? [{
            id: "suggestions",
            label: user.pending_suggestions ? `Suggestions (${user.pending_suggestions})` : "Suggestions",
          }] : []),
          { id: "tags", label: "Tags" },
        ]
      : []),
    ...(canSelfUpdate ? [{ id: "updates", label: "Updates" }, { id: "share-app", label: "Share the app" }] : []),
    { id: "devices", label: "Devices" },
  ]

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className={`mb-4 ${s.dark ? "text-white" : "text-gray-900"}`}>Settings</h1>
      {sections.length > 3 && (
        <nav className="flex flex-wrap gap-2 mb-6" aria-label="Settings sections">
          {sections.map((section) => (
            // Buttons, not href="#id" links: the page's <base href> would send those to the home page
            <button
              key={section.id}
              type="button"
              className={s.chip(false)}
              onClick={() => {
                document.getElementById(section.id)?.scrollIntoView({ behavior: "smooth" })
                const { pathname, search } = window.location
                window.history.replaceState(window.history.state, "", `${pathname}${search}#${section.id}`)
              }}
            >
              {section.label}
            </button>
          ))}
        </nav>
      )}

      {features.serverOutdated && (
        <div className={`${s.card} border-amber-500/50`}>
          <h2 className={s.heading}>Your server is older than this app</h2>
          <p className={`text-sm ${s.muted}`}>
            Scores, chapter read marks, series details and some reader options need a newer server, so
            they're hidden for now. {user?.is_owner ? "Update the server to use them." : "Ask the server's owner to update it."}
          </p>
        </div>
      )}

      <div id="account" className="scroll-mt-20">
        <AccountSection>
          <div className={`mt-8 pt-6 border-t ${s.divider}`}>
            <div className="flex flex-wrap gap-3">
              <button className={s.button} onClick={() => logout().then(() => navigate("/connect"))}>
                Log out
              </button>
            </div>
            <p className={`text-sm mt-4 ${s.muted}`}>
              Server: {server || window.location.origin}
              {serverInfo?.version && ` (myMangaLib ${serverInfo.version})`}
            </p>
            <Link to="/about" className="inline-block mt-2 mr-4 text-sm text-brand-500 hover:text-brand-400">
              About this app
            </Link>
            {serverInfo?.classic_ui_path && (
              <a
                href={`${serverBase()}${serverInfo.classic_ui_path}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-2 text-sm text-brand-500 hover:text-brand-400"
              >
                Open the classic web interface
              </a>
            )}
          </div>
        </AccountSection>
      </div>

      {showServers && <ServersSection />}

      <section id="appearance" className={`${s.card} scroll-mt-20`}>
        <h2 className={s.heading}>Appearance</h2>
        <p className={`text-sm mb-4 ${s.muted}`}>Applies on this device.</p>
        <div className={`divide-y ${s.divider}`}>
          <SettingSwitch
            label="Dark theme"
            description="Dark backgrounds, easier on the eyes at night."
            checked={s.dark}
            onChange={toggleTheme}
          />
          <div className="py-3">
            <p className={s.text}>Accent color</p>
            <p className={`text-sm mt-0.5 mb-3 ${s.muted}`}>Used for buttons, links and highlights.</p>
            <div className="flex flex-wrap gap-3" role="radiogroup" aria-label="Accent color">
              {ACCENTS.map((option) => {
                const selected = option.id === accent
                return (
                  <button
                    key={option.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setAccent(option.id)}
                    className={`flex items-center gap-2 pl-2 pr-4 py-2 rounded-full border transition-colors ${
                      selected
                        ? "border-brand-500 bg-brand-600/15"
                        : s.dark
                          ? "border-gray-700 hover:bg-gray-800"
                          : "border-gray-300 hover:bg-gray-100"
                    }`}
                  >
                    <span
                      className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs"
                      style={{ background: option.swatch }}
                    >
                      {selected ? "✓" : ""}
                    </span>
                    <span className={s.text}>{option.label}</span>
                  </button>
                )
              })}
            </div>
          </div>
          <div className="py-3">
            <p className={s.text}>Page background</p>
            <p className={`text-sm mt-0.5 mb-3 ${s.muted}`}>
              {PAGE_BACKGROUNDS.find((option) => option.id === pageBackground)?.description}
            </p>
            <div className="flex flex-wrap gap-3" role="radiogroup" aria-label="Page background">
              {PAGE_BACKGROUNDS.map((option) => {
                const selected = option.id === pageBackground
                return (
                  <button
                    key={option.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setPageBackground(option.id)}
                    className={`px-4 py-2 rounded-full border transition-colors ${
                      selected
                        ? "border-brand-500 bg-brand-600/15"
                        : s.dark
                          ? "border-gray-700 hover:bg-gray-800"
                          : "border-gray-300 hover:bg-gray-100"
                    }`}
                  >
                    <span className={s.text}>{option.label}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </section>

      <section id="reading" className={`${s.card} scroll-mt-20`}>
        <h2 className={s.heading}>Reading</h2>
        <div className={`divide-y ${s.divider}`}>
          <SettingSwitch
            label="Read right to left"
            description="For Japanese manga: the next page is on the left, and swiping right turns forward. Series can override this from the reader, or from their details."
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
          <div className="py-3">
            <p className={s.text}>Page size</p>
            <p className={`text-sm mt-0.5 mb-3 ${s.muted}`}>
              How single pages fit the screen. Webtoons in vertical scroll always fill the width.
            </p>
            <div className="flex flex-wrap gap-3" role="radiogroup" aria-label="Page size">
              {FIT_MODES.map((option) => {
                const selected = option.id === fitMode
                return (
                  <button
                    key={option.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    title={option.description}
                    onClick={() => {
                      setFitMode(option.id)
                      setFitModeState(option.id)
                    }}
                    className={`px-4 py-2 rounded-full border transition-colors ${
                      selected
                        ? "border-brand-500 bg-brand-600/15"
                        : s.dark
                          ? "border-gray-700 hover:bg-gray-800"
                          : "border-gray-300 hover:bg-gray-100"
                    }`}
                  >
                    <span className={s.text}>
                      {selected ? "✓ " : ""}
                      {option.label}
                    </span>
                  </button>
                )
              })}
            </div>
            <p className={`text-sm mt-2 ${s.muted}`}>
              {FIT_MODES.find((option) => option.id === fitMode).description}
            </p>
          </div>
        </div>
        <p className={`text-sm mt-3 ${s.muted}`}>
          In the reader, tap or click the left or right edge, swipe, or use the arrow keys to turn
          pages. The bottom bar jumps to any page or chapter, and the page size button changes how
          pages fit the screen. Webtoons (long strips) open in vertical scroll automatically; the mode
          button in the reader changes it for a series.
        </p>
      </section>

      {canUseAppLock && <AppLockSection />}

      {user?.is_owner && (
        <div id="library" className="scroll-mt-20">
          <LibrarySection />
        </div>
      )}
      {user?.is_owner && features.serverUpdates && (
        <div id="server-updates" className="scroll-mt-20">
          <ServerUpdatesSection />
        </div>
      )}
      {user?.is_admin && (
        <>
          <div id="users" className="scroll-mt-20">
            <UsersSection />
          </div>
          {features.seriesDetails && (
            <div id="suggestions" className="scroll-mt-20">
              <SuggestionsSection />
            </div>
          )}
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
      {canSelfUpdate && (
        <div id="share-app" className="scroll-mt-20">
          <ShareAppSection />
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
                      <span className="ml-2 text-xs text-brand-500">This device</span>
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
