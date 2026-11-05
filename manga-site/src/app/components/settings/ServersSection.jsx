import { useState } from "react"
import { useNavigate } from "react-router"
import { Check, Server } from "lucide-react"
import { serverAddress, serverLabel, useAuth } from "../../context/AuthContext"
import { useStyles } from "../../hooks/useStyles"

// Saved servers: each keeps its own login, so switching doesn't need the password again
export function ServersSection() {
  const { server, servers, switchServer, forgetServer } = useAuth()
  const navigate = useNavigate()
  const s = useStyles()
  const [confirming, setConfirming] = useState(null)

  const switchTo = (url) => {
    // Pages from one server mean nothing on the other, so start at home
    navigate("/", { replace: true })
    switchServer(url)
  }

  const remove = async (url) => {
    setConfirming(null)
    if (url === server) navigate("/", { replace: true })
    await forgetServer(url)
  }

  return (
    <section id="servers" className={`${s.card} scroll-mt-20`}>
      <h2 className={s.heading}>Servers</h2>
      <p className={`text-sm mb-4 ${s.muted}`}>
        Servers saved on this device. Each one remembers its login, so you can switch without logging in again.
      </p>
      <ul className={`divide-y ${s.divider}`}>
        {servers.map((entry) => {
          const isCurrent = entry.url === server
          return (
            <li key={entry.url} className="py-3 flex flex-wrap items-center gap-3">
              <Server className="w-5 h-5 shrink-0 text-brand-500" aria-hidden="true" />
              {/* On a phone the buttons go below the name, so the address stays readable */}
              <div className="min-w-48 flex-1">
                <p className={`truncate ${s.text}`}>
                  {serverLabel(entry)}
                  {isCurrent && (
                    <span className="ml-2 inline-flex items-center gap-1 text-xs text-brand-500">
                      <Check className="w-3.5 h-3.5" aria-hidden="true" /> In use
                    </span>
                  )}
                </p>
                <p className={`text-sm break-all ${s.muted}`}>{serverAddress(entry.url)}</p>
                <p className={`text-sm ${s.muted}`}>
                  {entry.token ? (entry.username ? `Logged in as ${entry.username}` : "Logged in") : "Not logged in"}
                </p>
              </div>
              <div className="flex gap-2 ml-auto">
                {!isCurrent && (
                  <button className={s.primaryButton} onClick={() => switchTo(entry.url)}>
                    Switch
                  </button>
                )}
                {/* The site the web app came from can't be removed: it's always there */}
                {entry.url &&
                  (confirming === entry.url ? (
                    <>
                      <button className={s.dangerButton} onClick={() => remove(entry.url)}>
                        Remove
                      </button>
                      <button className={s.button} onClick={() => setConfirming(null)}>
                        Keep
                      </button>
                    </>
                  ) : (
                    <button className={s.button} onClick={() => setConfirming(entry.url)}>
                      Remove
                    </button>
                  ))}
              </div>
            </li>
          )
        })}
      </ul>
      <button
        className={`${s.button} mt-4`}
        onClick={() => navigate("/connect", { state: { addServer: true } })}
      >
        Add a server
      </button>
    </section>
  )
}
