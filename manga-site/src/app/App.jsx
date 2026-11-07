import { useEffect } from "react"
import { RouterProvider } from "react-router"
import { setupBackButton, setupDeepLinks } from "./lib/native"
import { joinPath, parseJoinLink } from "./lib/share"
import { Toaster } from "sonner"
import { router } from "./routes"
import { ThemeProvider, useTheme } from "./context/ThemeContext"
import { AuthProvider } from "./context/AuthContext"
import { UpdateProvider } from "./context/UpdateContext"
import { DownloadsProvider } from "./context/DownloadsContext"
import { UpdatingOverlay } from "./components/UpdatingOverlay"
import { AppLockProvider, useAppLock } from "./context/AppLockContext"
import { LockScreen } from "./components/LockScreen"

function ThemedToaster() {
  const { theme } = useTheme()
  return <Toaster theme={theme} position="bottom-center" />
}

// While locked, the app stays mounted (the reader keeps its page) but can't be reached
function Lockable({ children }) {
  const { locked } = useAppLock()
  return (
    <>
      <div inert={locked ? "" : undefined} aria-hidden={locked ? true : undefined}>
        {children}
      </div>
      <LockScreen />
    </>
  )
}

export default function App() {
  useEffect(setupBackButton, [])
  useEffect(
    () =>
      setupDeepLinks((url) => {
        const link = parseJoinLink(url)
        if (link) router.navigate(joinPath(link))
      }),
    [],
  )
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppLockProvider>
          <DownloadsProvider>
            <UpdateProvider>
              <Lockable>
                <RouterProvider router={router} />
                <ThemedToaster />
                <UpdatingOverlay />
              </Lockable>
            </UpdateProvider>
          </DownloadsProvider>
        </AppLockProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
