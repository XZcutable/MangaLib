import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { BookOpen, Smartphone } from "lucide-react"
import { useAuth } from "../context/AuthContext"
import { useStyles } from "../hooks/useStyles"
import { api, normalizeServerUrl } from "../lib/api"
import { BASE_PATH } from "../lib/base"
import { isNative } from "../lib/storage"
import { ANDROID_DOWNLOAD_URL, appLink } from "../lib/share"
import { Tenma } from "../components/Tenma"
import { PageBackground, useScene } from "../components/PageBackground"

const thisSite = () => `${window.location.origin}${BASE_PATH}`

// Opened from a shared link or QR code: <server>/join?code=... in a browser, or /join?server=...&code=...
// in the app (deep link or scan). With a code it creates an account through the invite; without one it
// just adds the server and goes to its login screen.
export function Join() {
  const auth = useAuth()
  const navigate = useNavigate()
  const s = useStyles()
  const scene = useScene()
  const [params] = useSearchParams()
  const code = params.get("code")

  // The server the link is for. In a browser it's this site unless the link names another one.
  const named = params.get("server") ? normalizeServerUrl(params.get("server")) : null
  const target = named && !(!isNative && named === thisSite()) ? named : isNative ? null : ""

  const [details, setDetails] = useState(null) // invite info, or server info when there's no code
  const [problem, setProblem] = useState(null)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [waiting, setWaiting] = useState(false)
  const [newAccountAnyway, setNewAccountAnyway] = useState(false)

  useEffect(() => {
    if (target === null) {
      setProblem("This link doesn't say which server it's for.")
      return
    }
    const load = code ? api.inviteInfo(code, target) : api.serverInfo(target)
    load
      .then((data) => {
        if (!code && data?.name !== "myMangaLib") throw new Error("That address isn't a myMangaLib server")
        setDetails(data)
      })
      .catch((error) =>
        setProblem(error.status === 0 ? "Can't reach the server. Check you're on the right network." : error.message),
      )
  }, [target, code])

  // Already logged in to this server on this device?
  const savedLogin = auth.servers.find((entry) => entry.url === target && entry.token)
  const loggedInHere = savedLogin && !newAccountAnyway
  const siteName = details?.site_name || "this server"

  const run = async (action) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  // Makes the link's server the current one, without using a saved login there
  const selectTarget = async () => {
    if (savedLogin) {
      if (auth.server !== target) await auth.switchServer(target)
      await auth.logout()
    } else if (auth.server !== target || auth.status === "needs-server") {
      await auth.connect(target)
    }
  }

  const openSaved = () => run(async () => {
    if (auth.server !== target) await auth.switchServer(target)
    navigate("/", { replace: true })
  })

  const goToLogin = () => run(async () => {
    if (auth.server !== target || auth.status === "needs-server") await auth.connect(target)
    navigate("/connect", { replace: true })
  })

  const submit = (event) => {
    event.preventDefault()
    const name = username.trim()
    setUsername(name)
    run(async () => {
      await selectTarget()
      const { user } = await auth.register(name, password, code)
      if (!user.approved) {
        setWaiting(true)
        return
      }
      await auth.login(name, password)
      navigate("/", { replace: true })
    })
  }

  // In a phone's browser, offer to open the link in the Android app instead
  const offerApp = !isNative && /Android/i.test(navigator.userAgent) && target !== null

  return (
    <div className={`relative isolate min-h-screen flex items-center justify-center px-4 py-10 ${s.dark ? "bg-gray-950" : "bg-gray-50"}`}>
      <PageBackground scene={scene} />
      <div className="relative w-full max-w-sm flex flex-col items-center">
        <Tenma pose="wave" size="h-44" className="mb-2" />
        <div className={`w-full ${s.card} mb-0`}>
          <div className="flex items-center gap-2 mb-6">
            <BookOpen className="w-6 h-6 text-brand-500" />
            <span className={`font-semibold ${s.dark ? "text-white" : "text-gray-900"}`}>{siteName}</span>
          </div>

          {problem ? (
            <div className="space-y-4">
              <h1 className={s.heading}>This link doesn't work</h1>
              <p className={`text-sm ${s.muted}`}>{problem}</p>
              <Link to="/connect" className={`block text-center ${s.button}`}>Go to the login screen</Link>
            </div>
          ) : !details || auth.status === "loading" ? (
            <p className={s.muted}>Checking the link…</p>
          ) : waiting ? (
            <div className="space-y-4">
              <h1 className={s.heading}>Account created</h1>
              <p className={`text-sm ${s.muted}`}>
                An admin of {siteName} needs to approve it before you can log in. Try logging in again later.
              </p>
              <Link to="/connect" replace className={`block text-center ${s.primaryButton}`}>Go to the login screen</Link>
            </div>
          ) : loggedInHere ? (
            <div className="space-y-4">
              <h1 className={s.heading}>You're already on {siteName}</h1>
              <p className={`text-sm ${s.muted}`}>
                This device is logged in there{savedLogin.username ? ` as ${savedLogin.username}` : ""}.
              </p>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <button disabled={busy} onClick={openSaved} className={`w-full ${s.primaryButton}`}>
                Open {siteName}
              </button>
              {code && details.valid && (
                <button onClick={() => setNewAccountAnyway(true)} className="w-full text-sm text-brand-500">
                  Log out and create a new account
                </button>
              )}
            </div>
          ) : !code ? (
            <div className="space-y-4">
              <h1 className={s.heading}>Join {siteName}</h1>
              <p className={`text-sm ${s.muted}`}>
                {details.registration_open
                  ? "Log in, or create an account if you don't have one yet."
                  : "Log in with your account. To get a new account, ask someone there for an invite."}
              </p>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <button disabled={busy} onClick={goToLogin} className={`w-full ${s.primaryButton}`}>
                Continue
              </button>
            </div>
          ) : !details.valid ? (
            <div className="space-y-4">
              <h1 className={s.heading}>This invite can't be used</h1>
              <p className={`text-sm ${s.muted}`}>{details.message}. Ask the person who invited you for a new one.</p>
              <button disabled={busy} onClick={goToLogin} className={`w-full ${s.button}`}>
                I already have an account
              </button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div>
                <h1 className={`${s.heading} mb-1`}>You're invited</h1>
                <p className={`text-sm ${s.muted}`}>
                  {details.invited_by ? `${details.invited_by} invited you to ${siteName}. ` : ""}
                  Create an account to start reading.
                  {!details.approved_on_join && " An admin approves new accounts before they can log in."}
                </p>
              </div>
              <div>
                <label htmlFor="join-username" className={`block text-sm mb-1 ${s.text}`}>Username</label>
                <input
                  id="join-username"
                  className={`w-full ${s.input}`}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  autoCapitalize="none"
                  autoCorrect="off"
                  required
                  autoFocus
                />
              </div>
              <div>
                <label htmlFor="join-password" className={`block text-sm mb-1 ${s.text}`}>Password</label>
                <input
                  id="join-password"
                  type="password"
                  className={`w-full ${s.input}`}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="new-password"
                  required
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <button disabled={busy} className={`w-full ${s.primaryButton}`}>
                {busy ? "Please wait…" : "Create account"}
              </button>
              <button type="button" disabled={busy} onClick={goToLogin} className="w-full text-sm text-brand-500">
                I already have an account
              </button>
            </form>
          )}

          {offerApp && (
            <div className={`mt-6 pt-4 border-t text-sm ${s.divider}`}>
              <a href={appLink(target || thisSite(), code)} className="flex items-center justify-center gap-2 text-brand-500">
                <Smartphone className="w-4 h-4" /> Open in the app
              </a>
              <p className={`mt-2 text-center text-xs ${s.muted}`}>
                Don't have it?{" "}
                <a href={ANDROID_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer" className="text-brand-500">
                  Get the Android app
                </a>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
