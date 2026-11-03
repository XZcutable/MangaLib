import { useEffect } from "react"
import { RouterProvider } from "react-router"
import { setupBackButton } from "./lib/native"
import { Toaster } from "sonner"
import { router } from "./routes"
import { ThemeProvider, useTheme } from "./context/ThemeContext"
import { AuthProvider } from "./context/AuthContext"
import { UpdateProvider } from "./context/UpdateContext"

function ThemedToaster() {
  const { theme } = useTheme()
  return <Toaster theme={theme} position="bottom-center" />
}

export default function App() {
  useEffect(setupBackButton, [])
  return (
    <ThemeProvider>
      <AuthProvider>
        <UpdateProvider>
          <RouterProvider router={router} />
          <ThemedToaster />
        </UpdateProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
