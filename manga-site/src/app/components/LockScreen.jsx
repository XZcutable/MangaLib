import { useAuth } from "../context/AuthContext"
import { useAppLock } from "../context/AppLockContext"
import { useTheme } from "../context/ThemeContext"
import { Tenma } from "./Tenma"

// Covers the app until the phone's unlock succeeds. While settings load ("pending") it's blank, so
// nothing shows through on a cold start.
export function LockScreen() {
  const { locked, error, unlock } = useAppLock()
  const { siteName } = useAuth()
  const { theme } = useTheme()
  if (!locked) return null
  const dark = theme === "dark"
  return (
    <div
      role="alertdialog"
      aria-label={`${siteName} is locked`}
      className={`fixed inset-0 z-[1100] flex items-center justify-center px-4 text-center ${
        dark ? "bg-gray-950 text-gray-100" : "bg-gray-50 text-gray-900"
      }`}
    >
      {locked === true && (
        <div className="max-w-sm">
          <Tenma pose="sleeping" size="h-64 sm:h-80" className="mx-auto mb-4" />
          <h2 className="mb-2 text-xl font-semibold">{siteName} is locked</h2>
          <p className={`mb-5 ${dark ? "text-gray-400" : "text-gray-600"}`}>
            {error && error.code !== "canceled" ? error.message : "Unlock with your face, fingerprint or screen lock."}
          </p>
          <button className="rounded-md bg-brand-600 px-6 py-2 text-white hover:bg-brand-700" onClick={unlock}>
            Unlock
          </button>
        </div>
      )}
    </div>
  )
}
