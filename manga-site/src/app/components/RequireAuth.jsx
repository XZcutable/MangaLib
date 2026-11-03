import { Navigate, Outlet, useLocation } from "react-router"
import { useAuth } from "../context/AuthContext"
import { useTheme } from "../context/ThemeContext"

// Routes inside need a logged-in user. Anything else goes to the connect screen.
export function RequireAuth() {
  const { status } = useAuth()
  const { theme } = useTheme()
  const location = useLocation()

  if (status === "loading") {
    return <div className={`min-h-screen ${theme === "dark" ? "bg-gray-950" : "bg-gray-50"}`} />
  }
  if (status !== "ready") {
    return <Navigate to="/connect" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}
