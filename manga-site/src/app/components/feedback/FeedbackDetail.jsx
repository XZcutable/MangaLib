import { useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"
import { useStyles } from "../../hooks/useStyles"
import { api, imageUrl, parseServerDate } from "../../lib/api"
import { KIND_LABELS, STATUS_ACTIONS, STATUS_LABELS, statusTone } from "../../lib/feedback"

const TONES = {
  green: "bg-green-600/15 text-green-500 border-green-600/40",
  gray: "bg-gray-500/15 text-gray-400 border-gray-500/40",
  amber: "bg-amber-500/15 text-amber-500 border-amber-500/40",
  brand: "bg-brand-600/15 text-brand-500 border-brand-600/40",
}

export function StatusChip({ status }) {
  return (
    <span className={`inline-block text-xs px-2 py-0.5 rounded-full border whitespace-nowrap ${TONES[statusTone(status)]}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

const formatDate = (value) => (value ? parseServerDate(value).toLocaleString() : "")
const CLOSED = ["done", "declined", "duplicate"]

function Section({ title, children }) {
  const s = useStyles()
  return (
    <div className="mt-4">
      <p className={s.subheading}>{title}</p>
      {children}
    </div>
  )
}

function LogBlock({ title, text }) {
  const s = useStyles()
  if (!text) return null
  return (
    <details className="mt-4">
      <summary className={`cursor-pointer text-sm font-semibold ${s.dark ? "text-gray-300" : "text-gray-700"}`}>
        {title} ({text.split("\n").length} lines)
      </summary>
      <pre
        className={`mt-2 p-3 rounded-md text-xs overflow-auto max-h-80 whitespace-pre-wrap break-all ${
          s.dark ? "bg-gray-950 text-gray-300" : "bg-gray-100 text-gray-800"
        }`}
      >
        {text}
      </pre>
    </details>
  )
}

function eventText(event) {
  const who = event.author === "agent" ? "Review agent" : event.author === "system" ? "" : event.username ?? "Someone"
  if (event.kind === "status") {
    const to = STATUS_LABELS[event.data?.to] ?? event.data?.to
    return event.author === "system" ? `Moved back to ${to} after the reply` : `${who} changed the status to ${to}`
  }
  if (event.kind === "triage") return `${who}: review (${event.data?.verdict ?? "done"})`
  if (event.kind === "plan") return `${who} wrote a plan`
  if (event.kind === "plan_decision") return `${who}: ${STATUS_LABELS[event.data?.decision] ?? "decision"} on the plan`
  return who
}

function Timeline({ events }) {
  const s = useStyles()
  if (!events?.length) return null
  return (
    <Section title="Updates">
      <ol className="space-y-3">
        {events.map((event) => (
          <li
            key={event.id}
            className={`text-sm border-l-2 pl-3 ${event.kind === "plan" ? "border-brand-500" : s.dark ? "border-gray-700" : "border-gray-300"}`}
          >
            <p className={`text-xs ${s.muted}`}>
              {eventText(event)} · {formatDate(event.created)}
            </p>
            {event.body && <p className={`mt-1 whitespace-pre-wrap break-words ${s.text}`}>{event.body}</p>}
          </li>
        ))}
      </ol>
    </Section>
  )
}

// One feedback item with its screenshots, logs and updates. `staff` shows the owner/admin actions.
export function FeedbackDetail({ item, staff = false, onChange, onDelete }) {
  const s = useStyles()
  const [reply, setReply] = useState("")
  const [note, setNote] = useState("")
  const [busy, setBusy] = useState(false)
  const [zoomed, setZoomed] = useState(null)

  const run = async (action, success) => {
    setBusy(true)
    try {
      const result = await action()
      if (result?.feedback) onChange?.(result.feedback)
      if (success) toast.success(success)
      return true
    } catch (error) {
      toast.error(error.message)
      return false
    } finally {
      setBusy(false)
    }
  }

  const sendReply = async () => {
    if (await run(() => api.commentFeedback(item.id, reply.trim()), "Reply sent")) setReply("")
  }
  const changeStatus = async (status) => {
    const done = await run(() => api.setFeedbackStatus(item.id, status, note.trim()), STATUS_LABELS[status])
    if (done) setNote("")
  }
  const remove = async () => {
    const question = staff && !item.mine ? "Delete this feedback for everyone?" : "Withdraw this feedback?"
    if (!window.confirm(question)) return
    if (await run(() => api.deleteFeedback(item.id), staff && !item.mine ? "Deleted" : "Withdrawn")) onDelete?.(item)
  }

  const canReply = staff || !CLOSED.includes(item.status)
  const canDelete = staff || (item.mine && item.status === "new")
  const plan = staff && item.status === "plan_ready"

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip status={item.status} />
        <span className={`text-xs ${s.muted}`}>
          {KIND_LABELS[item.kind] ?? item.kind}
          {staff && ` · from ${item.username ?? "a removed account"}`} · {formatDate(item.created)}
        </span>
      </div>
      {item.manga_title && (
        <p className={`text-sm mt-2 ${s.text}`}>
          Series:{" "}
          {item.manga_id ? (
            <Link to={`/manga/${item.manga_id}`} className="text-brand-500 hover:text-brand-400">
              {item.manga_title}
            </Link>
          ) : (
            `${item.manga_title} (removed)`
          )}
          {item.chapter != null && `, chapter ${item.chapter}`}
        </p>
      )}

      {item.body && <p className={`mt-3 whitespace-pre-wrap break-words ${s.text}`}>{item.body}</p>}
      {item.steps && (
        <Section title="Steps to reproduce">
          <p className={`text-sm whitespace-pre-wrap break-words ${s.text}`}>{item.steps}</p>
        </Section>
      )}
      {(item.expected || item.actual) && (
        <div className="grid sm:grid-cols-2 gap-x-4">
          {item.expected && (
            <Section title="Expected">
              <p className={`text-sm whitespace-pre-wrap break-words ${s.text}`}>{item.expected}</p>
            </Section>
          )}
          {item.actual && (
            <Section title="What happened">
              <p className={`text-sm whitespace-pre-wrap break-words ${s.text}`}>{item.actual}</p>
            </Section>
          )}
        </div>
      )}

      {item.attachments?.length > 0 && (
        <Section title="Screenshots">
          <div className="flex flex-wrap gap-3">
            {item.attachments.map((attachment) => (
              <button key={attachment.id} type="button" onClick={() => setZoomed(imageUrl(attachment.url))}>
                <img
                  src={imageUrl(attachment.url)}
                  alt="Screenshot"
                  className={`h-32 w-auto max-w-40 object-contain rounded-md border ${s.divider}`}
                />
              </button>
            ))}
          </div>
        </Section>
      )}

      <LogBlock title="App log" text={item.client_log} />
      <LogBlock title="Server errors" text={item.server_log} />
      {item.context && (
        <LogBlock
          title="Device and versions"
          text={Object.entries(item.context)
            .filter(([, value]) => value !== null && value !== "")
            .map(([key, value]) => `${key}: ${value}`)
            .join("\n")}
        />
      )}

      <Timeline events={item.events} />

      {canReply && (
        <Section title={staff && !item.mine ? `Reply to ${item.username ?? "the sender"}` : "Add a reply"}>
          <textarea
            className={`${s.input} w-full`}
            rows={2}
            maxLength={5000}
            value={reply}
            onChange={(event) => setReply(event.target.value)}
            placeholder={item.status === "needs_info" && !staff ? "Answer the question above" : "Write a reply"}
          />
          <button className={`${s.button} mt-2`} disabled={busy || !reply.trim()} onClick={sendReply}>
            Send reply
          </button>
        </Section>
      )}

      {staff && item.allowed_statuses?.length > 0 && (
        <Section title={plan ? "Decide on the plan" : "Change status"}>
          <textarea
            className={`${s.input} w-full`}
            rows={2}
            maxLength={5000}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note, shown with the status change"
          />
          <div className="flex flex-wrap gap-2 mt-2">
            {item.allowed_statuses.map((status) => (
              <button
                key={status}
                className={status === "approved" || status === "done" ? s.primaryButton : s.button}
                disabled={busy || (status === "needs_info" && !note.trim())}
                title={status === "needs_info" && !note.trim() ? "Write the question in the note first" : undefined}
                onClick={() => changeStatus(status)}
              >
                {STATUS_ACTIONS[status] ?? STATUS_LABELS[status]}
              </button>
            ))}
          </div>
        </Section>
      )}

      {canDelete && (
        <button className={`${s.dangerButton} mt-4`} disabled={busy} onClick={remove}>
          {staff && !item.mine ? "Delete" : "Withdraw"}
        </button>
      )}

      {zoomed && (
        <button
          type="button"
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4"
          onClick={() => setZoomed(null)}
          aria-label="Close screenshot"
        >
          <img src={zoomed} alt="Screenshot" className="max-w-full max-h-full object-contain" />
        </button>
      )}
    </div>
  )
}
