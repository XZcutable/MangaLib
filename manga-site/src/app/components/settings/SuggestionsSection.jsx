import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"
import { useAuth } from "../../context/AuthContext"
import { useStyles } from "../../hooks/useStyles"
import { api, parseServerDate } from "../../lib/api"
import { FIELD_LABELS, formatValue, waitForJob } from "../../lib/metadata"

// Admins review the series details users have suggested
export function SuggestionsSection() {
  const s = useStyles()
  const { setUser } = useAuth()
  const [suggestions, setSuggestions] = useState(null)
  const [busy, setBusy] = useState(null)

  const load = useCallback(
    () =>
      api
        .suggestions()
        .then(({ suggestions }) => {
          setSuggestions(suggestions)
          // Keep the navbar badge in step with the list
          setUser((current) =>
            current && current.pending_suggestions !== suggestions.length
              ? { ...current, pending_suggestions: suggestions.length }
              : current,
          )
        })
        .catch((error) => toast.error(error.message)),
    [setUser],
  )
  useEffect(() => {
    load()
  }, [load])

  const review = async (suggestion, approve) => {
    setBusy(suggestion.id)
    try {
      const { job } = await api.reviewSuggestion(suggestion.id, approve)
      await load()
      if (approve && job) {
        const done = await waitForJob(job)
        toast.success(`Approved. ${done.message ?? "Files updated"}.`)
      } else {
        toast.success(approve ? "Approved" : "Rejected")
      }
    } catch (error) {
      toast.error(error.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className={s.card}>
      <h2 className={s.heading}>Suggested changes</h2>
      {suggestions === null ? (
        <p className={s.muted}>Loading…</p>
      ) : suggestions.length === 0 ? (
        <p className={s.muted}>Nothing waiting. Suggestions from readers show up here.</p>
      ) : (
        <ul className={`divide-y ${s.divider}`}>
          {suggestions.map((suggestion) => (
            <li key={suggestion.id} className="py-4">
              <p className={s.text}>
                <Link to={`/manga/${suggestion.manga_id}`} className="text-brand-500 hover:text-brand-400">
                  {suggestion.manga_title ?? "Removed series"}
                </Link>
              </p>
              <p className={`text-xs mb-3 ${s.muted}`}>
                From {suggestion.username ?? "a removed account"}
                {suggestion.created && `, ${parseServerDate(suggestion.created).toLocaleString()}`}
              </p>
              <dl className="space-y-2 mb-3">
                {Object.entries(suggestion.changes).map(([key, value]) => (
                  <div key={key} className="text-sm">
                    <dt className={s.muted}>{FIELD_LABELS[key] ?? key}</dt>
                    <dd className="grid sm:grid-cols-2 gap-1 sm:gap-3 mt-0.5">
                      <span className={`line-through break-words whitespace-pre-wrap ${s.muted}`}>
                        {formatValue(key, suggestion.current?.[key])}
                      </span>
                      <span className={`break-words whitespace-pre-wrap ${s.text}`}>{formatValue(key, value)}</span>
                    </dd>
                  </div>
                ))}
              </dl>
              <div className="flex gap-3">
                <button
                  className={s.primaryButton}
                  disabled={busy !== null}
                  onClick={() => review(suggestion, true)}
                >
                  {busy === suggestion.id ? "Working…" : "Approve"}
                </button>
                <button className={s.button} disabled={busy !== null} onClick={() => review(suggestion, false)}>
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
