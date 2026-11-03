import { Search, ChevronDown, Menu, Moon, Sun, X } from "lucide-react"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router"
import { useState, useRef, useEffect } from "react"
import { useTheme } from "../context/ThemeContext"
import { useAuth } from "../context/AuthContext"

const navItems = [
  { label: "Home", path: "/" },
  { label: "Latest", path: "/latest" },
  { label: "All", path: "/all" },
  { label: "Random", path: "/random" },
  { label: "Unread", path: "/unread" },
]
const dropdownItems = [
  { label: "Settings", path: "/settings" },
  { label: "History", path: "/history" },
  { label: "Favorites", path: "/favorites" },
  { label: "To Read", path: "/bookmarks" },
  { label: "Log Out", path: "/logout" },
]

function SearchBox({ className = "", autoFocus = false, onDone }) {
  const { theme } = useTheme()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const location = useLocation()
  const [value, setValue] = useState(location.pathname === "/search" ? (params.get("q") ?? "") : "")

  const submit = (event) => {
    event.preventDefault()
    const q = value.trim()
    if (!q) return
    navigate(`/search?q=${encodeURIComponent(q)}`)
    onDone?.()
  }

  return (
    <form onSubmit={submit} className={`relative ${className}`} role="search">
      <input
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Search manga..."
        autoFocus={autoFocus}
        enterKeyHint="search"
        className={`w-full pl-10 pr-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent ${
          theme === "dark"
            ? "bg-gray-800 border-gray-700 text-white placeholder-gray-400"
            : "bg-white border-gray-300 text-gray-900 placeholder-gray-500"
        }`}
      />
      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
    </form>
  )
}

export function Navbar() {
  const location = useLocation()
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const dropdownRef = useRef(null)
  const { theme, toggleTheme } = useTheme()
  const { user } = useAuth()
  const dark = theme === "dark"

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Close the phone menu after navigating
  useEffect(() => {
    setIsMenuOpen(false)
    setIsSearchOpen(false)
  }, [location.pathname, location.search])

  const linkClass = (path) =>
    `px-3 py-2 rounded-md transition-colors ${
      location.pathname === path
        ? "bg-blue-600 text-white"
        : dark
          ? "text-gray-300 hover:bg-gray-800 hover:text-white"
          : "text-gray-700 hover:bg-gray-100"
    }`
  const iconButton = `p-2 rounded-md transition-colors ${
    dark ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-100 text-gray-700"
  }`

  const themeButton = (
    <button onClick={toggleTheme} className={iconButton} aria-label="Toggle theme">
      {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
    </button>
  )

  return (
    <nav
      className={`${
        dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
      } border-b sticky top-0 z-50 pt-[env(safe-area-inset-top)]`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Wide screens */}
        <div className="hidden lg:flex items-center justify-between h-16">
          <div className="flex items-center gap-6">
            {navItems.map((item) => (
              <Link key={item.path} to={item.path} className={linkClass(item.path)}>
                {item.label}
              </Link>
            ))}
          </div>

          <div className="flex items-center gap-4">
            <SearchBox className="w-64" />
            {themeButton}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                  dark ? "hover:bg-gray-800" : "hover:bg-gray-100"
                }`}
                aria-expanded={isDropdownOpen}
              >
                <span className={dark ? "text-gray-300" : "text-gray-700"}>{user?.username}</span>
                <ChevronDown className={`w-4 h-4 ${dark ? "text-gray-400" : "text-gray-500"}`} />
              </button>

              {isDropdownOpen && (
                <div
                  className={`absolute right-0 mt-2 w-48 rounded-md shadow-lg border py-1 ${
                    dark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
                  }`}
                >
                  {dropdownItems.map((item) => (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={() => setIsDropdownOpen(false)}
                      className={`block px-4 py-2 transition-colors ${
                        dark
                          ? "text-gray-300 hover:bg-gray-700 hover:text-white"
                          : "text-gray-700 hover:bg-gray-100"
                      }`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Phones and tablets */}
        <div className="lg:hidden">
          <div className="flex items-center justify-between h-14 gap-2">
            <Link to="/" className={`font-semibold ${dark ? "text-white" : "text-gray-900"}`}>
              myMangaLib
            </Link>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsSearchOpen(!isSearchOpen)}
                className={iconButton}
                aria-label="Search"
                aria-expanded={isSearchOpen}
              >
                <Search className="w-5 h-5" />
              </button>
              {themeButton}
              <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className={iconButton}
                aria-label="Menu"
                aria-expanded={isMenuOpen}
              >
                {isMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {isSearchOpen && (
            <div className="pb-3">
              <SearchBox autoFocus onDone={() => setIsSearchOpen(false)} />
            </div>
          )}

          {isMenuOpen && (
            <div className="pb-3 grid grid-cols-2 gap-1">
              {[...navItems, ...dropdownItems].map((item) => (
                <Link key={item.path} to={item.path} className={linkClass(item.path)}>
                  {item.label}
                </Link>
              ))}
              <p className={`col-span-2 px-3 pt-2 text-sm ${dark ? "text-gray-500" : "text-gray-500"}`}>
                Signed in as {user?.username}
              </p>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
