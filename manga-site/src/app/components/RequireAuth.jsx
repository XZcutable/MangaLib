import { Navigate, Outlet, useLocation } from "react-router"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"
import { ChooseUsername } from "./ChooseUsername"

// Routes inside need a logged-in user. Anything else goes to the connect screen.
// A user who has to change their username sees only that until it's done.
export function RequireAuth() {
  const { status, loggedOutOnPurpose, user } = useAuth()
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
  if (user?.must_change_username) return <ChooseUsername />
  return <Outlet />
}
