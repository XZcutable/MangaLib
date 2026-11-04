import { useEffect } from "react"
import { RouterProvider } from "react-router"
import { setupBackButton } from "./lib/native"
import { Toaster } from "sonner"
import { router } from "./routes"
import { ThemeProvider, useTheme } from "./context/ThemeContext"
import { AuthProvider } from "./context/AuthContext"
import { UpdateProvider } from "./context/UpdateContext"
import { DownloadsProvider } from "./context/DownloadsContext"

function ThemedToaster() {
  const { theme } = useTheme()
  return <Toaster theme={theme} position="bottom-center" />
}

export default function App() {
  useEffect(setupBackButton, [])
  return (
    <ThemeProvider>
      <AuthProvider>
        <DownloadsProvider>
          <UpdateProvider>
            <RouterProvider router={router} />
            <ThemedToaster />
          </UpdateProvider>
        </DownloadsProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
