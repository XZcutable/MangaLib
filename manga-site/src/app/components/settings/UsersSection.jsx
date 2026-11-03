import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { useAuth } from "../../context/AuthContext"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"

const ROLES = ["user", "moderator", "admin"]

// Admin: approve sign-ups and add accounts. Only the owner changes roles.
export function UsersSection() {
  const s = useStyles()
  const { user: me } = useAuth()
  const [users, setUsers] = useState(null)
  const [newUser, setNewUser] = useState({ username: "", password: "" })

  const load = useCallback(() => {
    api.users().then(({ users }) => setUsers(users)).catch((error) => toast.error(error.message))
  }, [])
  useEffect(load, [load])

  const update = async (user, changes) => {
    try {
      const { user: updated } = await api.updateUser(user.id, changes)
      setUsers((list) => list.map((item) => (item.id === updated.id ? updated : item)))
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
      load()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const pending = users?.filter((user) => !user.approved) ?? []

  return (
    <section className={s.card}>
      <h2 className={s.heading}>
        Users
        {pending.length > 0 && (
          <span className="ml-2 text-xs align-middle px-2 py-0.5 rounded-full bg-blue-600 text-white">
            {pending.length} waiting
          </span>
        )}
      </h2>

      {users === null ? (
        <p className={s.muted}>Loading…</p>
      ) : (
        <ul className={`border rounded-md divide-y mb-6 ${s.divider}`}>
          {users.map((user) => {
            const locked = user.is_owner || user.id === me?.id
            return (
              <li key={user.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
                <div className="flex-1 min-w-[8rem]">
                  <p className={s.text}>{user.username}</p>
                  <p className={`text-xs ${s.muted}`}>
                    {user.approved ? user.role : "Waiting for approval"}
                    {user.id === me?.id && " • you"}
                  </p>
                </div>
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
                {!locked &&
                  (user.approved ? (
                    <button className={`${s.button} py-1`} onClick={() => update(user, { approved: false })}>
                      Revoke
                    </button>
                  ) : (
                    <button className={`${s.primaryButton} py-1`} onClick={() => update(user, { approved: true })}>
                      Approve
                    </button>
                  ))}
              </li>
            )
          })}
        </ul>
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
