import { useState } from "react"
import { toast } from "sonner"
import { useAuth } from "../../context/AuthContext"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"

export function AccountSection({ children }) {
  const s = useStyles()
  const { user, setUser } = useAuth()
  const [username, setUsername] = useState(user?.username ?? "")
  const [passwords, setPasswords] = useState({ current: "", next: "", repeat: "" })
  const [busy, setBusy] = useState(false)

  const run = async (action, success) => {
    setBusy(true)
    try {
      await action()
      toast.success(success)
    } catch (error) {
      toast.error(error.message)
    } finally {
      setBusy(false)
    }
  }

  const saveUsername = (event) => {
    event.preventDefault()
    run(async () => {
      const { user } = await api.changeUsername(username)
      setUser(user)
    }, "Username changed")
  }

  const savePassword = (event) => {
    event.preventDefault()
    if (passwords.next !== passwords.repeat) {
      toast.error("The new passwords don't match")
      return
    }
    run(async () => {
      await api.changePassword(passwords.current, passwords.next)
      setPasswords({ current: "", next: "", repeat: "" })
    }, "Password changed. Other devices will need to log in again.")
  }

  const setPassword = (key) => (event) => setPasswords({ ...passwords, [key]: event.target.value })

  return (
    <section className={s.card}>
      <h2 className={s.heading}>Account</h2>
      <p className={`text-sm mb-6 ${s.muted}`}>
        Signed in as <span className={s.text}>{user?.username}</span> ({user?.role})
      </p>

      <div className="grid gap-8 md:grid-cols-2">
        <form onSubmit={saveUsername} className="space-y-3">
          <h3 className={s.subheading}>Username</h3>
          <input
            className={`${s.input} w-full`}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
          <button className={s.button} disabled={busy || username === user?.username}>
            Change username
          </button>
        </form>

        <form onSubmit={savePassword} className="space-y-3">
          <h3 className={s.subheading}>Password</h3>
          <input
            type="password"
            className={`${s.input} w-full`}
            placeholder="Current password"
            value={passwords.current}
            onChange={setPassword("current")}
            autoComplete="current-password"
            required
          />
          <input
            type="password"
            className={`${s.input} w-full`}
            placeholder="New password"
            value={passwords.next}
            onChange={setPassword("next")}
            autoComplete="new-password"
            required
          />
          <input
            type="password"
            className={`${s.input} w-full`}
            placeholder="Repeat new password"
            value={passwords.repeat}
            onChange={setPassword("repeat")}
            autoComplete="new-password"
            required
          />
          <p className={`text-xs ${s.muted}`}>
            6-20 characters with a number, an uppercase letter, a lowercase letter and a symbol.
          </p>
          <button className={s.button} disabled={busy}>
            Change password
          </button>
        </form>
      </div>

      {children}
    </section>
  )
}
