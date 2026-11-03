import { Navigate, Outlet, useLocation } from "react-router"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"

// Routes inside need a logged-in user. Anything else goes to the connect screen.
export function RequireAuth() {
  const { status, loggedOutOnPurpose } = useAuth()
  const { theme } = useTheme()
  const location = useLocation()

  if (status === "loading") {
    return <div className={`min-h-screen ${theme === "dark" ? "bg-gray-950" : "bg-gray-50"}`} />
  }
  if (status !== "ready") {
    // Remember the page only when the login expired or someone opened a link while logged out.
    // After logging out on purpose, the next login starts at home.
    const from = loggedOutOnPurpose ? undefined : location.pathname + location.search
    return <Navigate to="/connect" replace state={from ? { from } : undefined} />
  }
  return <Outlet />
}
