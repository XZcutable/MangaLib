import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useLocation, useSearchParams } from "react-router"
import { ChevronDown, ImagePlus, X } from "lucide-react"
import { toast } from "sonner"
import { useAuth } from "../context/AuthContext"
import { useStyles } from "../hooks/useStyles"
import { api, parseServerDate } from "../lib/api"
import { feedbackContext, KINDS, KIND_LABELS, MAX_SCREENSHOT_MB, MAX_SCREENSHOTS } from "../lib/feedback"
import { logText } from "../lib/logBuffer"
import { FeedbackDetail, StatusChip } from "../components/feedback/FeedbackDetail"

const EMPTY = { title: "", body: "", steps: "", expected: "", actual: "" }

function Field({ label, hint, children }) {
  const s = useStyles()
  return (
    <label className="block mb-4">
      <span className={`block text-sm font-medium mb-1 ${s.text}`}>{label}</span>
      {children}
      {hint && <span className={`block text-xs mt-1 ${s.muted}`}>{hint}</span>}
    </label>
  )
}

// Picks the series a content problem is about
function SeriesPicker({ value, onChange }) {
  const s = useStyles()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState([])

  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setResults([])
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api
        .search(q, { limit: 8 }, controller.signal)
        .then(({ items }) => setResults(items))
        .catch(() => {})
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  if (value) {
    return (
      <div className={`flex items-center gap-2 ${s.text}`}>
        <span className="truncate">{value.title}</span>
        <button type="button" className={`${s.button} py-1 text-sm`} onClick={() => onChange(null)}>
          Change
        </button>
      </div>
    )
  }
  return (
    <div>
      <input
        className={`${s.input} w-full`}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search for the series"
      />
      {results.length > 0 && (
        <ul className={`mt-1 rounded-md border divide-y ${s.divider}`}>
          {results.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`w-full text-left px-3 py-2 text-sm ${s.text} ${s.dark ? "hover:bg-gray-800" : "hover:bg-gray-100"}`}
                onClick={() => onChange({ id: item.id, title: item.title })}
              >
                {item.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Screenshots({ files, setFiles }) {
  const s = useStyles()
  const previews = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files])
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews])

  const add = (event) => {
    const picked = Array.from(event.target.files ?? [])
    event.target.value = ""
    const tooBig = picked.filter((file) => file.size > MAX_SCREENSHOT_MB * 1024 * 1024)
    if (tooBig.length) toast.error(`Screenshots can be at most ${MAX_SCREENSHOT_MB} MB each`)
    const next = [...files, ...picked.filter((file) => !tooBig.includes(file))]
    if (next.length > MAX_SCREENSHOTS) toast.error(`You can attach up to ${MAX_SCREENSHOTS} screenshots`)
    setFiles(next.slice(0, MAX_SCREENSHOTS))
  }

  return (
    <div className="mb-4">
      <p className={`text-sm font-medium mb-1 ${s.text}`}>Screenshots</p>
      <div className="flex flex-wrap gap-3">
        {previews.map((url, index) => (
          <div key={url} className="relative">
            <img src={url} alt={`Screenshot ${index + 1}`} className={`h-24 w-auto max-w-32 object-contain rounded-md border ${s.divider}`} />
            <button
              type="button"
              className="absolute -top-2 -right-2 rounded-full bg-gray-900 text-white p-1"
              onClick={() => setFiles(files.filter((_, i) => i !== index))}
              aria-label={`Remove screenshot ${index + 1}`}
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        {files.length < MAX_SCREENSHOTS && (
          <label className={`${s.button} h-24 w-24 flex flex-col items-center justify-center gap-1 cursor-pointer text-xs`}>
            <ImagePlus className="w-5 h-5" />
            Add
            <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="hidden" onChange={add} />
          </label>
        )}
      </div>
      <p className={`text-xs mt-1 ${s.muted}`}>
        Up to {MAX_SCREENSHOTS} PNG, JPEG or WebP images. Take a screenshot first, then add it here.
      </p>
    </div>
  )
}

function MyFeedback({ items, onChanged }) {
  const s = useStyles()
  const [openId, setOpenId] = useState(null)
  const [detail, setDetail] = useState(null)

  const open = async (id) => {
    if (openId === id) return setOpenId(null)
    setOpenId(id)
    setDetail(null)
    try {
      setDetail((await api.feedback(id)).feedback)
    } catch (error) {
      toast.error(error.message)
      setOpenId(null)
    }
  }

  if (!items?.length) return null
  return (
    <section className={s.card}>
      <h2 className={s.heading}>Your feedback</h2>
      <ul className={`divide-y ${s.divider}`}>
        {items.map((item) => (
          <li key={item.id} className="py-3">
            <button type="button" className="w-full text-left flex items-start gap-3" onClick={() => open(item.id)}>
              <div className="min-w-0 flex-1">
                <p className={`truncate ${s.text}`}>{item.title}</p>
                <p className={`text-xs mt-0.5 ${s.muted}`}>
                  {KIND_LABELS[item.kind] ?? item.kind} · {item.created && parseServerDate(item.created).toLocaleDateString()}
                </p>
              </div>
              <StatusChip status={item.status} />
              <ChevronDown className={`w-4 h-4 mt-1 shrink-0 transition-transform ${openId === item.id ? "rotate-180" : ""} ${s.muted}`} />
            </button>
            {openId === item.id && (
              <div className={`mt-3 pt-3 border-t ${s.divider}`}>
                {detail ? (
                  <FeedbackDetail
                    item={detail}
                    onChange={(updated) => {
                      setDetail(updated)
                      onChanged()
                    }}
                    onDelete={() => {
                      setOpenId(null)
                      onChanged()
                    }}
                  />
                ) : (
                  <p className={s.muted}>Loading…</p>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

// /feedback: send a bug report, idea or content request, and follow what happened to earlier ones.
// ?kind=content_problem&manga=<id>&chapter=<n> fills the form in (from the series page and reader).
export function Feedback() {
  const s = useStyles()
  const { siteName } = useAuth()
  const location = useLocation()
  const [params] = useSearchParams()
  const fromPath = location.state?.from ?? null

  const [kind, setKind] = useState(() => (KIND_LABELS[params.get("kind")] ? params.get("kind") : "bug"))
  const [fields, setFields] = useState(EMPTY)
  const [series, setSeries] = useState(null)
  const [chapter, setChapter] = useState(() => params.get("chapter") ?? "")
  const [files, setFiles] = useState([])
  const [includeLogs, setIncludeLogs] = useState(true)
  const [showDetails, setShowDetails] = useState(false)
  const [sending, setSending] = useState(false)
  const [mine, setMine] = useState(null)

  // The series from the link, so its title shows
  useEffect(() => {
    const id = Number(params.get("manga"))
    if (!id) return
    api
      .manga(id)
      .then((manga) => setSeries({ id: manga.id, title: manga.title }))
      .catch(() => {})
  }, [params])

  const loadMine = useCallback(() => {
    api
      .myFeedback()
      .then(({ feedback }) => setMine(feedback))
      .catch(() => {})
  }, [])
  useEffect(loadMine, [loadMine])

  const set = (key) => (event) => setFields((current) => ({ ...current, [key]: event.target.value }))
  const context = useMemo(() => feedbackContext(fromPath), [fromPath])
  const log = showDetails ? logText() : ""
  const isBug = kind === "bug"
  const isProblem = kind === "content_problem"
  const canAttach = isBug || isProblem

  const submit = async (event) => {
    event.preventDefault()
    if (isProblem && !series) return toast.error("Pick the series first")
    const report = {
      kind,
      title: fields.title.trim(),
      body: fields.body.trim(),
      context,
      ...(isBug && {
        steps: fields.steps.trim(),
        expected: fields.expected.trim(),
        actual: fields.actual.trim(),
        client_log: includeLogs ? logText() : undefined,
      }),
      ...(isProblem && { manga_id: series.id, chapter: chapter ? Number(chapter) : undefined }),
    }
    setSending(true)
    try {
      await api.sendFeedback(report, canAttach ? files : [])
      toast.success("Thanks! Your feedback was sent.")
      setFields(EMPTY)
      setFiles([])
      loadMine()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setSending(false)
    }
  }

  const current = KINDS.find((entry) => entry.id === kind)

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className={`mb-2 ${s.dark ? "text-white" : "text-gray-900"}`}>Send feedback</h1>
      <p className={`mb-6 ${s.muted}`}>Goes to the people who run {siteName}. You'll see their replies below.</p>

      <section className={s.card}>
        <div className="flex flex-wrap gap-2 mb-2" role="radiogroup" aria-label="What is it about?">
          {KINDS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              role="radio"
              aria-checked={kind === entry.id}
              className={s.chip(kind === entry.id)}
              onClick={() => setKind(entry.id)}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <p className={`text-sm mb-6 ${s.muted}`}>{current?.hint}</p>

        {kind === "details" ? (
          <div className={s.text}>
            <p className="mb-3">
              Series details are fixed on the series page: open it and use <strong>Suggest edit</strong>. Your
              change is shown to an admin to approve.
            </p>
            {series && (
              <Link to={`/manga/${series.id}`} state={{ editDetails: true }} className={s.primaryButton}>
                Suggest an edit to {series.title}
              </Link>
            )}
          </div>
        ) : (
          <form onSubmit={submit}>
            {isProblem && (
              <>
                <Field label="Series">
                  <SeriesPicker value={series} onChange={setSeries} />
                </Field>
                <Field label="Chapter (optional)">
                  <input
                    className={`${s.input} w-32`}
                    type="number"
                    min="1"
                    value={chapter}
                    onChange={(event) => setChapter(event.target.value)}
                  />
                </Field>
              </>
            )}
            <Field label={kind === "content_request" ? "Series name" : isProblem ? "Short summary (optional)" : "Title"}>
              <input
                className={`${s.input} w-full`}
                value={fields.title}
                onChange={set("title")}
                maxLength={150}
                required={!isProblem}
                placeholder={
                  isBug ? "e.g. The reader skips a page" : kind === "content_request" ? "e.g. Frieren" : isProblem ? "e.g. Page 12 is blank" : "In a few words"
                }
              />
            </Field>
            <Field
              label={isBug ? "What happened?" : kind === "content_request" ? "Anything that helps find it (optional)" : "Details"}
              hint={kind === "content_request" ? "Author, volume, a link…" : undefined}
            >
              <textarea className={`${s.input} w-full`} rows={4} value={fields.body} onChange={set("body")} maxLength={10000} required={isBug} />
            </Field>

            {isBug && (
              <>
                <Field label="Steps to reproduce" hint="What you did, one step per line.">
                  <textarea
                    className={`${s.input} w-full`}
                    rows={4}
                    value={fields.steps}
                    onChange={set("steps")}
                    maxLength={5000}
                    placeholder={"1. Open a series\n2. Tap Continue reading\n3. Swipe to the next page"}
                  />
                </Field>
                <div className="grid sm:grid-cols-2 gap-x-4">
                  <Field label="What you expected">
                    <textarea className={`${s.input} w-full`} rows={2} value={fields.expected} onChange={set("expected")} maxLength={2000} />
                  </Field>
                  <Field label="What happened instead">
                    <textarea className={`${s.input} w-full`} rows={2} value={fields.actual} onChange={set("actual")} maxLength={2000} />
                  </Field>
                </div>
              </>
            )}

            {canAttach && <Screenshots files={files} setFiles={setFiles} />}

            {isBug && (
              <div className="mb-4">
                <label className={`flex items-center gap-2 text-sm ${s.text}`}>
                  <input type="checkbox" checked={includeLogs} onChange={(event) => setIncludeLogs(event.target.checked)} />
                  Include the app's recent log
                </label>
                <p className={`text-xs mt-1 ${s.muted}`}>
                  Recent errors and failed requests, with passwords and login tokens removed. The server also adds its
                  own recent errors. Only the owner can see either.{" "}
                  <button type="button" className="text-brand-500 hover:text-brand-400" onClick={() => setShowDetails(!showDetails)}>
                    {showDetails ? "Hide" : "See what's sent"}
                  </button>
                </p>
                {showDetails && (
                  <pre
                    className={`mt-2 p-3 rounded-md text-xs overflow-auto max-h-64 whitespace-pre-wrap break-all ${
                      s.dark ? "bg-gray-950 text-gray-300" : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {Object.entries(context)
                      .filter(([, value]) => value !== null)
                      .map(([key, value]) => `${key}: ${value}`)
                      .join("\n")}
                    {includeLogs && `\n\n${log || "(the log is empty)"}`}
                  </pre>
                )}
              </div>
            )}

            <button type="submit" className={s.primaryButton} disabled={sending}>
              {sending ? "Sending…" : "Send"}
            </button>
          </form>
        )}
      </section>

      <MyFeedback items={mine} onChanged={loadMine} />
    </div>
  )
}
