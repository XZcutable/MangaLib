import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { useAuth } from "../../context/AuthContext"
import { useStyles } from "../../hooks/useStyles"
import { api, parseServerDate } from "../../lib/api"
import { SettingSwitch } from "./SettingSwitch"

// How often the open Users section checks for new sign-ups
const REFRESH_MS = 10_000

const ROLES = ["user", "moderator", "admin"]

// Admins approve or reject sign-ups and add accounts. The owner also controls sign-ups and roles.
export function UsersSection() {
  const s = useStyles()
  const { user: me, setUser, refreshServerInfo } = useAuth()
  const [users, setUsers] = useState(null)
  const [config, setConfig] = useState(null)
  const [newUser, setNewUser] = useState({ username: "", password: "" })
  const [publicUrl, setPublicUrl] = useState("")

  const load = useCallback(
    ({ quiet = false } = {}) =>
      api
        .users()
        .then(({ users }) => {
          setUsers(users)
          // Keep the navbar badge in step with the list
          const waiting = users.filter((user) => !user.approved).length
          setUser((current) =>
            current && current.pending_users !== waiting ? { ...current, pending_users: waiting } : current,
          )
        })
        .catch((error) => !quiet && toast.error(error.message)),
    [setUser],
  )

  // New sign-ups show up while this page is open, without reloading
  useEffect(() => {
    load()
    const refresh = () => document.visibilityState === "visible" && load({ quiet: true })
    const timer = setInterval(refresh, REFRESH_MS)
    document.addEventListener("visibilitychange", refresh)
    return () => {
      clearInterval(timer)
      document.removeEventListener("visibilitychange", refresh)
    }
  }, [load])

  useEffect(() => {
    if (me?.is_owner) api.serverConfig().then(setConfig).catch(() => {})
  }, [me?.is_owner])
  useEffect(() => {
    if (config) setPublicUrl(config.public_url ?? "")
  }, [config?.public_url])

  const savePublicUrl = async (event) => {
    event.preventDefault()
    try {
      const updated = await api.updateServerConfig({ public_url: publicUrl })
      setConfig(updated)
      refreshServerInfo().catch(() => {})
      toast.success(updated.public_url ? "Invite links now use this address" : "Invite links use the address each person is connected to")
    } catch (error) {
      toast.error(error.message)
    }
  }

  // Reloading also updates the "waiting" count in the navbar
  const afterChange = () => load()

  const update = async (user, changes) => {
    try {
      await api.updateUser(user.id, changes)
      afterChange()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const remove = async (user, question) => {
    if (!confirm(question)) return
    try {
      await api.deleteUser(user.id)
      afterChange()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const change = async (key, value) => {
    try {
      setConfig(await api.updateServerConfig({ [key]: value }))
      refreshServerInfo().catch(() => {})
    } catch (error) {
      toast.error(error.message)
    }
  }

  const create = async (event) => {
    event.preventDefault()
    try {
      await api.register(newUser.username, newUser.password)
      toast.success(`Added ${newUser.username}`)
      setNewUser({ username: "", password: "" })
      afterChange()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const pending = users?.filter((user) => !user.approved) ?? []
  const members = users?.filter((user) => user.approved) ?? []
  const joined = (user) =>
    user.date_created ? `Signed up ${parseServerDate(user.date_created).toLocaleDateString()}` : "Signed up"

  return (
    <section className={s.card}>
      <h2 className={s.heading}>Users</h2>

      {config && (
        <div className="mb-8">
          <h3 className={s.subheading}>Sign-ups</h3>
          <div className={`divide-y ${s.divider}`}>
            <SettingSwitch
              label="Allow sign-ups"
              description="Anyone who can reach this server can create an account. When off, only admins add accounts."
              checked={config.allow_new_users}
              onChange={(value) => change("allow_new_users", value)}
            />
            <SettingSwitch
              label="Approve new accounts automatically"
              description="When off, new accounts wait below until an admin approves them."
              disabledReason="Turn on sign-ups first. Accounts added by admins are always approved."
              checked={config.auto_approve_new_users}
              onChange={(value) => change("auto_approve_new_users", value)}
              disabled={!config.allow_new_users}
            />
          </div>
          {"public_url" in config && (
            <form onSubmit={savePublicUrl} className="mt-4">
              <label htmlFor="public-url" className={`block mb-1 ${s.text}`}>
                Public address
              </label>
              <div className="flex flex-wrap gap-2">
                <input
                  id="public-url"
                  className={`${s.input} flex-1 min-w-[10rem]`}
                  value={publicUrl}
                  onChange={(event) => setPublicUrl(event.target.value)}
                  maxLength={200}
                  placeholder="https://manga.example.com"
                  inputMode="url"
                  autoCapitalize="none"
                  autoCorrect="off"
                />
                <button className={s.button} disabled={publicUrl.trim().replace(/\/+$/, "") === config.public_url}>
                  Save
                </button>
              </div>
              <p className={`text-xs mt-1 ${s.muted}`}>
                The address people use to reach this server from anywhere. Invite links and QR codes use it.
                Leave it empty to share the address each person is connected to.
              </p>
            </form>
          )}
        </div>
      )}

      {users === null ? (
        <p className={s.muted}>Loading…</p>
      ) : (
        <>
          <h3 className={s.subheading}>
            Waiting for approval
            {pending.length > 0 && (
              <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-brand-600 text-white">
                {pending.length}
              </span>
            )}
          </h3>
          {pending.length === 0 ? (
            <p className={`text-sm mb-8 ${s.muted}`}>No one is waiting.</p>
          ) : (
            <ul className={`border rounded-md divide-y mb-8 ${s.divider}`}>
              {pending.map((user) => (
                <li key={user.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
                  <div className="flex-1 min-w-[8rem]">
                    <p className={s.text}>{user.username}</p>
                    <p className={`text-xs ${s.muted}`}>{joined(user)}</p>
                  </div>
                  <button
                    className={`${s.primaryButton} py-1`}
                    onClick={() => update(user, { approved: true })}
                  >
                    Approve
                  </button>
                  <button
                    className={`${s.dangerButton} py-1`}
                    onClick={() => remove(user, `Reject ${user.username}? Their account is deleted.`)}
                  >
                    Reject
                  </button>
                </li>
              ))}
            </ul>
          )}

          <h3 className={s.subheading}>Members</h3>
          <ul className={`border rounded-md divide-y mb-6 ${s.divider}`}>
            {members.map((user) => {
              const locked = user.is_owner || user.id === me?.id
              return (
                <li key={user.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
                  <div className="flex-1 min-w-[8rem]">
                    <p className={s.text}>{user.username}</p>
                    <p className={`text-xs ${s.muted}`}>
                      {user.role}
                      {user.id === me?.id && " • you"}
                      {user.must_change_username && (
                        <span className="text-amber-500"> • must choose a new username</span>
                      )}
                    </p>
                  </div>
                  {!locked && (
                    <button
                      className={`${s.button} py-1`}
                      onClick={() => update(user, { must_change_username: !user.must_change_username })}
                      title={
                        user.must_change_username
                          ? "Let them keep their current username"
                          : "They can't use their account until they pick a new username"
                      }
                    >
                      {user.must_change_username ? "Keep username" : "Require new username"}
                    </button>
                  )}
                  {!locked && me?.is_owner && (
                    <select
                      className={`${s.input} py-1`}
                      value={user.role}
                      onChange={(event) => update(user, { role: event.target.value })}
                      aria-label={`Role for ${user.username}`}
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </select>
                  )}
                  {!locked && (
                    <button
                      className={`${s.button} py-1`}
                      onClick={() => update(user, { approved: false })}
                      title="Signs them out and moves them back to waiting"
                    >
                      Suspend
                    </button>
                  )}
                  {!locked && me?.is_owner && (
                    <button
                      className={`${s.dangerButton} py-1`}
                      onClick={() =>
                        remove(user, `Delete ${user.username}? Their account and reading history are removed.`)
                      }
                    >
                      Delete
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        </>
      )}

      <form onSubmit={create} className="flex flex-wrap gap-2">
        <input
          className={`${s.input} flex-1 min-w-[10rem]`}
          placeholder="New username"
          value={newUser.username}
          onChange={(event) => setNewUser({ ...newUser, username: event.target.value })}
          autoComplete="off"
          required
        />
        <input
          type="password"
          className={`${s.input} flex-1 min-w-[10rem]`}
          placeholder="Password"
          value={newUser.password}
          onChange={(event) => setNewUser({ ...newUser, password: event.target.value })}
          autoComplete="new-password"
          required
        />
        <button className={s.button}>Add user</button>
      </form>
      <p className={`text-xs mt-2 ${s.muted}`}>Users you add are approved straight away.</p>
    </section>
  )
}
