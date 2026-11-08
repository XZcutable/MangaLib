import {
  Book,
  BookmarkCheck,
  ChevronDown,
  Download,
  Folder,
  Heart,
  History,
  House,
  LogOut,
  MessageSquareWarning,
  Moon,
  QrCode,
  Rss,
  Search,
  Server,
  Settings,
  Shuffle,
  Sparkles,
  Star,
  Sun,
  User,
} from "lucide-react"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router"
import { useState, useRef, useEffect, useLayoutEffect } from "react"
import { useTheme } from "../context/ThemeContext"
import { serverLabel, useAuth } from "../context/AuthContext"
import { offlineAvailable } from "../lib/offline"
import { useServerFeatures } from "../lib/features"
import { useSearchSuggestions } from "../hooks/useSearchSuggestions"
import { applySuggestion, blockedCharacter, contextAt, endContext, suggestionsFor } from "../lib/searchSyntax"

// Same icons as the classic interface. Like the classic navbar, the labels drop away on smaller
// screens and the icons stay, so every section is one tap away instead of hidden in a menu.
const navItems = [
  { label: "Home", path: "/", icon: House },
  { label: "Updated", path: "/latest", icon: Rss },
  { label: "New Releases", path: "/newest", icon: Sparkles },
  { label: "All", path: "/all", icon: Folder },
  { label: "Random", path: "/random", icon: Shuffle },
  { label: "Unread", path: "/unread", icon: Book },
]
const accountItems = [
  { label: "Settings", path: "/settings", icon: Settings },
  { label: "Favorites", path: "/favorites", icon: Heart },
  { label: "To Read", path: "/bookmarks", icon: BookmarkCheck },
  { label: "History", path: "/history", icon: History },
  { label: "Top Rated", path: "/top-rated", icon: Star },
  // Downloads only exist in the Android app
  ...(offlineAvailable ? [{ label: "Downloads", path: "/downloads", icon: Download }] : []),
  { label: "Share", path: "/share", icon: QrCode },
  // Bug reports, ideas and content requests (servers with API version 8)
  { label: "Send Feedback", path: "/feedback", icon: MessageSquareWarning },
  { label: "Log Out", path: "/logout", icon: LogOut },
]

function SearchBox({ className = "", autoFocus = false, onDone }) {
  const { theme } = useTheme()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const location = useLocation()
  const { searchSyntax } = useServerFeatures()
  const { load, sources } = useSearchSuggestions(searchSyntax)
  const inputRef = useRef(null)
  const pendingCaret = useRef(null)
  const [value, setValue] = useState(location.pathname === "/search" ? (params.get("q") ?? "") : "")
  const [caret, setCaret] = useState(value.length)
  const [focused, setFocused] = useState(false)
  const [closed, setClosed] = useState(false)
  const [active, setActive] = useState(-1)
  const [hint, setHint] = useState(null)
  const dark = theme === "dark"

  const context = searchSyntax ? contextAt(value, caret) : null
  const suggestions = focused && !closed ? suggestionsFor(context, sources) : []
  const open = suggestions.length > 0 || (focused && hint)

  useEffect(() => setActive(-1), [value, caret])
  // Puts the caret where a suggestion or a closed filter left it, before the next key is handled
  useLayoutEffect(() => {
    if (pendingCaret.current === null) return
    inputRef.current?.setSelectionRange(pendingCaret.current, pendingCaret.current)
    pendingCaret.current = null
  })
  useEffect(() => {
    if (!hint) return
    const timer = setTimeout(() => setHint(null), 2500)
    return () => clearTimeout(timer)
  }, [hint])

  const update = (text, position) => {
    setValue(text)
    setCaret(position)
    setClosed(false)
    pendingCaret.current = position
  }

  const change = (event) => {
    const text = event.target.value
    const position = event.target.selectionStart ?? text.length
    // One character typed at the caret: spaces close a filter, some keys refuse & (checked here rather
    // than on keydown because phone keyboards don't report which key was pressed)
    if (searchSyntax && text.length === value.length + 1 && position > 0) {
      const typed = text[position - 1]
      const old = position - 1
      if (text.slice(0, old) + text.slice(position) === value) {
        const blocked = blockedCharacter(contextAt(value, old), typed)
        if (blocked) {
          setHint(blocked)
          update(value, old)
          return
        }
        if (typed === " ") {
          const ended = endContext(value, old)
          if (ended) return update(ended.text, ended.caret)
        }
      }
    }
    setValue(text)
    setCaret(position)
    setClosed(false)
  }

  const choose = (suggestion) => {
    const next = applySuggestion(value, context, suggestion.insert)
    update(next.text, next.caret)
    inputRef.current?.focus()
  }

  const keyDown = (event) => {
    if (!suggestions.length) return
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault()
      const step = event.key === "ArrowDown" ? 1 : -1
      // -1 is "nothing picked", so Enter still searches
      setActive((index) => {
        const next = index + step
        if (next >= suggestions.length) return -1
        return next < -1 ? suggestions.length - 1 : next
      })
    } else if (event.key === "Tab" || (event.key === "Enter" && active >= 0)) {
      event.preventDefault()
      choose(suggestions[Math.max(active, 0)])
    } else if (event.key === "Escape") {
      event.preventDefault()
      setClosed(true)
    }
  }

  const submit = (event) => {
    event.preventDefault()
    const q = value.trim()
    if (!q) return
    navigate(`/search?q=${encodeURIComponent(q)}`)
    setClosed(true)
    onDone?.()
  }

  const listId = `search-suggestions${autoFocus ? "-menu" : ""}`
  return (
    <form onSubmit={submit} className={`relative ${className}`} role="search">
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={change}
        onSelect={(event) => setCaret(event.target.selectionStart ?? 0)}
        onKeyDown={keyDown}
        onFocus={() => {
          setFocused(true)
          load()
        }}
        onBlur={() => setFocused(false)}
        placeholder="Search manga..."
        aria-label="Search manga"
        autoFocus={autoFocus}
        enterKeyHint="search"
        autoComplete="off"
        autoCapitalize="off"
        spellCheck={false}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={suggestions.length > 0}
        aria-controls={listId}
        aria-activedescendant={active >= 0 && active < suggestions.length ? `${listId}-${active}` : undefined}
        className={`w-full pl-10 pr-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent ${
          dark
            ? "bg-gray-800 border-gray-700 text-white placeholder-gray-400"
            : "bg-white border-gray-300 text-gray-900 placeholder-gray-500"
        }`}
      />
      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
      {open && (
        <div
          className={`absolute left-0 right-0 top-full mt-1 z-50 rounded-md border shadow-lg overflow-hidden ${
            dark ? "bg-gray-900 border-gray-700" : "bg-white border-gray-200"
          }`}
        >
          {hint && <p className={`px-3 py-2 text-sm ${dark ? "text-amber-300" : "text-amber-700"}`}>{hint}</p>}
          {suggestions.length > 0 && (
            <ul id={listId} role="listbox" className="py-1 max-h-72 overflow-y-auto">
              {suggestions.map((suggestion, index) => (
                <li
                  key={suggestion.insert}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  // Keeps the focus (and the keyboard on phones) in the input
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(suggestion)}
                  className={`flex items-baseline gap-3 px-3 py-2 cursor-pointer text-sm ${
                    index === active
                      ? "bg-brand-600 text-white"
                      : dark
                        ? "text-gray-200 hover:bg-gray-800"
                        : "text-gray-800 hover:bg-gray-100"
                  }`}
                >
                  <span className="truncate">{suggestion.label}</span>
                  {suggestion.detail && (
                    <span className={`ml-auto shrink-0 text-xs ${index === active ? "text-white/80" : "text-gray-500"}`}>
                      {suggestion.detail}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </form>
  )
}

export function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const [isAccountOpen, setIsAccountOpen] = useState(false)
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const accountRef = useRef(null)
  const { theme, toggleTheme } = useTheme()
  const { user, server, servers, switchServer } = useAuth()
  const otherServers = servers.filter((entry) => entry.url !== server)
  const dark = theme === "dark"
  // Sign-ups, metadata suggestions and feedback waiting for an admin
  const pendingUsers = user?.pending_users ?? 0
  const pendingSuggestions = user?.pending_suggestions ?? 0
  const { ratings, feedback } = useServerFeatures()
  const menuItems = accountItems.filter(
    (item) => (ratings || item.path !== "/top-rated") && (feedback || item.path !== "/feedback"),
  )
  const pending = pendingUsers + pendingSuggestions + (user?.pending_feedback ?? 0)
  const pendingSection = pendingUsers > 0 ? "users" : pendingSuggestions > 0 ? "suggestions" : "feedback"

  useEffect(() => {
    function handleClickOutside(event) {
      if (accountRef.current && !accountRef.current.contains(event.target)) {
        setIsAccountOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Close the menu and search after navigating
  useEffect(() => {
    setIsAccountOpen(false)
    setIsSearchOpen(false)
  }, [location.pathname, location.search])

  const iconButton = `bounce-on-hover p-2 rounded-md transition-colors ${
    dark ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-100 text-gray-700"
  }`
  const menuRow = `bounce-on-hover w-full flex items-center gap-3 px-4 py-2 text-left transition-colors ${
    dark ? "text-gray-300 hover:bg-gray-700 hover:text-white" : "text-gray-700 hover:bg-gray-100"
  }`

  return (
    <nav
      className={`${
        dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
      } border-b sticky top-0 z-50 pt-[env(safe-area-inset-top)]`}
    >
      <div className="max-w-7xl mx-auto px-2 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 lg:h-16 gap-2">
          {/* Sections: icon and label on wide screens, icon only below that */}
          <div className="flex items-center gap-0.5 sm:gap-1 xl:gap-2">
            {navItems.map(({ label, path, icon: Icon }) => {
              const active = location.pathname === path
              return (
                <Link
                  key={path}
                  to={path}
                  title={label}
                  aria-label={label}
                  aria-current={active ? "page" : undefined}
                  className={`bounce-on-hover flex items-center gap-2 p-2 xl:px-3 rounded-md transition-colors ${
                    active
                      ? "bg-brand-600 text-white"
                      : dark
                        ? "text-gray-300 hover:bg-gray-800 hover:text-white"
                        : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <Icon className="bounce-icon w-5 h-5 shrink-0" aria-hidden="true" />
                  <span className="hidden xl:inline">{label}</span>
                </Link>
              )
            })}
          </div>

          <div className="flex items-center gap-0.5 sm:gap-2">
            <SearchBox className="hidden lg:block w-56 xl:w-64" />
            <button
              onClick={() => setIsSearchOpen(!isSearchOpen)}
              className={`${iconButton} lg:hidden`}
              aria-label="Search"
              title="Search"
              aria-expanded={isSearchOpen}
            >
              <Search className="bounce-icon w-5 h-5" />
            </button>

            <button
              onClick={toggleTheme}
              className={`${iconButton} hidden sm:block`}
              aria-label="Toggle theme"
              title="Toggle theme"
            >
              {dark ? <Sun className="bounce-icon w-5 h-5" /> : <Moon className="bounce-icon w-5 h-5" />}
            </button>

            {/* Account menu, like the classic user dropdown */}
            <div className="relative" ref={accountRef}>
              <button
                onClick={() => setIsAccountOpen(!isAccountOpen)}
                className={`bounce-on-hover relative flex items-center gap-1.5 p-2 sm:px-3 rounded-md transition-colors ${
                  dark ? "text-gray-300 hover:bg-gray-800" : "text-gray-700 hover:bg-gray-100"
                }`}
                aria-expanded={isAccountOpen}
                aria-label={`Account: ${user?.username ?? ""}`}
                title={user?.username}
              >
                <User className="bounce-icon w-5 h-5" aria-hidden="true" />
                <span className="hidden sm:inline max-w-32 truncate">{user?.username}</span>
                <ChevronDown className={`w-4 h-4 ${dark ? "text-gray-400" : "text-gray-500"}`} />
                {pending > 0 && (
                  <span
                    className={`absolute top-1.5 left-6 w-2.5 h-2.5 rounded-full bg-brand-500 ring-2 ${
                      dark ? "ring-gray-900" : "ring-white"
                    }`}
                    aria-label="Waiting for review"
                  />
                )}
              </button>

              {isAccountOpen && (
                <div
                  className={`absolute right-0 mt-2 w-56 rounded-md shadow-lg border py-1 ${
                    dark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
                  }`}
                >
                  <p className={`px-4 py-2 text-sm sm:hidden ${dark ? "text-gray-400" : "text-gray-500"}`}>
                    Signed in as {user?.username}
                  </p>
                  {menuItems.map(({ label, path, icon: Icon }) => {
                    const showCount = path === "/settings" && pending > 0
                    return (
                      <Link
                        key={path}
                        to={showCount ? `/settings#${pendingSection}` : path}
                        onClick={() => setIsAccountOpen(false)}
                        className={menuRow}
                      >
                        <Icon className="bounce-icon w-4 h-4 shrink-0" aria-hidden="true" />
                        {label}
                        {showCount && (
                          <span
                            className="ml-auto inline-flex min-w-5 h-5 px-1.5 items-center justify-center rounded-full bg-brand-600 text-white text-xs"
                            aria-label={`${pending} waiting for review`}
                          >
                            {pending}
                          </span>
                        )}
                      </Link>
                    )
                  })}
                  {/* The theme button doesn't fit the phone bar, so it lives here on small screens */}
                  <button onClick={toggleTheme} className={`${menuRow} sm:hidden`}>
                    {dark ? (
                      <Sun className="bounce-icon w-4 h-4" aria-hidden="true" />
                    ) : (
                      <Moon className="bounce-icon w-4 h-4" aria-hidden="true" />
                    )}
                    {dark ? "Light theme" : "Dark theme"}
                  </button>
                  {otherServers.length > 0 && (
                    <div className={`mt-1 pt-1 border-t ${dark ? "border-gray-700" : "border-gray-200"}`}>
                      <p className={`px-4 py-1 text-xs ${dark ? "text-gray-400" : "text-gray-500"}`}>Switch server</p>
                      {otherServers.map((entry) => (
                        <button
                          key={entry.url}
                          onClick={() => {
                            setIsAccountOpen(false)
                            // Pages from one server mean nothing on the other, so start at home
                            navigate("/", { replace: true })
                            switchServer(entry.url)
                          }}
                          className={menuRow}
                        >
                          <Server className="bounce-icon w-4 h-4 shrink-0" aria-hidden="true" />
                          <span className="truncate">{serverLabel(entry)}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {isSearchOpen && (
          <div className="pb-3 lg:hidden">
            <SearchBox autoFocus onDone={() => setIsSearchOpen(false)} />
          </div>
        )}
      </div>
    </nav>
  )
}
