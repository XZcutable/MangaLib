import { useEffect } from "react"
import { useNavigate } from "react-router"
import { useAuth } from "../context/AuthContext"

export function Logout() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  useEffect(() => {
    logout().then(() => navigate("/connect", { replace: true }))
  }, [logout, navigate])
  return null
}
