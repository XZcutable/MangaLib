import { useCallback, useEffect, useState } from "react"
import { ChevronDown, Paperclip } from "lucide-react"
import { toast } from "sonner"
import { useAuth } from "../../context/AuthContext"
import { useStyles } from "../../hooks/useStyles"
import { api, parseServerDate } from "../../lib/api"
import { KIND_LABELS } from "../../lib/feedback"
import { FeedbackDetail, StatusChip } from "../feedback/FeedbackDetail"

const FILTERS = [
  { id: "open", label: "Open" },
  { id: "plan_ready", label: "Plans to approve" },
  { id: "done", label: "Done" },
  { id: "all", label: "All" },
]

// The inbox: the owner sees every report; other admins see content requests and problems
export function FeedbackSection() {
  const s = useStyles()
  const { user, refreshUser } = useAuth()
  const [status, setStatus] = useState("open")
  const [kind, setKind] = useState("")
  const [items, setItems] = useState(null)
  const [kinds, setKinds] = useState([])
  const [openId, setOpenId] = useState(null)
  const [detail, setDetail] = useState(null)

  const load = useCallback(
    () =>
      api
        .feedbackInbox({ status, kind })
        .then((result) => {
          setItems(result.feedback)
          setKinds(result.kinds)
        })
        .catch((error) => toast.error(error.message)),
    [status, kind],
  )
  useEffect(() => {
    load()
  }, [load])

  const open = async (id) => {
    if (openId === id) {
      setOpenId(null)
      return
    }
    setOpenId(id)
    setDetail(null)
    try {
      setDetail((await api.feedbackForStaff(id)).feedback)
    } catch (error) {
      toast.error(error.message)
      setOpenId(null)
    }
  }

  const changed = (item) => {
    setDetail(item)
    load()
    refreshUser() // the navbar badge
  }
  const deleted = () => {
    setOpenId(null)
    load()
    refreshUser()
  }

  // The agent's plans only exist for the owner's kinds
  const filters = user?.is_owner ? FILTERS : FILTERS.filter((filter) => filter.id !== "plan_ready")

  return (
    <section className={s.card}>
      <h2 className={s.heading}>Feedback</h2>
      <p className={`text-sm mb-4 ${s.muted}`}>
        {user?.is_owner
          ? "Bug reports, ideas and content requests from people on this server."
          : "Series requests and problems with series. Bug reports and ideas go to the owner."}
      </p>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {filters.map((filter) => (
          <button key={filter.id} type="button" className={s.chip(status === filter.id)} onClick={() => setStatus(filter.id)}>
            {filter.label}
          </button>
        ))}
        {kinds.length > 1 && (
          <select
            className={`${s.input} py-1 text-sm`}
            value={kind}
            onChange={(event) => setKind(event.target.value)}
            aria-label="Kind"
          >
            <option value="">Every kind</option>
            {kinds.map((id) => (
              <option key={id} value={id}>
                {KIND_LABELS[id] ?? id}
              </option>
            ))}
          </select>
        )}
      </div>

      {items === null ? (
        <p className={s.muted}>Loading…</p>
      ) : items.length === 0 ? (
        <p className={s.muted}>{status === "open" ? "Nothing waiting." : "Nothing here."}</p>
      ) : (
        <ul className={`divide-y ${s.divider}`}>
          {items.map((item) => (
            <li key={item.id} className="py-3">
              <button
                type="button"
                className="w-full text-left flex items-start gap-3"
                onClick={() => open(item.id)}
                aria-expanded={openId === item.id}
              >
                <div className="min-w-0 flex-1">
                  <p className={`truncate ${s.text}`}>{item.title}</p>
                  <p className={`text-xs mt-0.5 ${s.muted}`}>
                    {KIND_LABELS[item.kind] ?? item.kind} · {item.username ?? "removed account"} ·{" "}
                    {item.created && parseServerDate(item.created).toLocaleDateString()}
                    {item.attachment_count > 0 && (
                      <Paperclip className="inline w-3 h-3 ml-1" aria-label="Has screenshots" />
                    )}
                  </p>
                </div>
                <StatusChip status={item.status} />
                <ChevronDown className={`w-4 h-4 mt-1 shrink-0 transition-transform ${openId === item.id ? "rotate-180" : ""} ${s.muted}`} />
              </button>
              {openId === item.id && (
                <div className={`mt-3 pt-3 border-t ${s.divider}`}>
                  {detail ? (
                    <FeedbackDetail item={detail} staff onChange={changed} onDelete={deleted} />
                  ) : (
                    <p className={s.muted}>Loading…</p>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
