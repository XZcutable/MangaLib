import { useState } from "react"
import { toast } from "sonner"
import { useStyles } from "../hooks/useStyles"
import { api } from "../lib/api"
import { METADATA_FIELDS, waitForJob } from "../lib/metadata"
import { LANGUAGES } from "../lib/languages"

const toForm = (metadata) =>
  Object.fromEntries(
    METADATA_FIELDS.map(({ key, type }) => {
      const value = metadata[key]
      if (type === "list") return [key, (value ?? []).join(", ")]
      if (type === "year") return [key, value ? String(value) : ""]
      return [key, value ?? ""]
    }),
  )

const fromForm = (form) =>
  Object.fromEntries(
    METADATA_FIELDS.map(({ key, type }) => {
      const value = form[key]
      if (type === "list")
        return [key, value.split(",").map((part) => part.trim()).filter(Boolean)]
      if (type === "year") return [key, value.trim() ? Number(value.trim()) : null]
      if (type === "direction" || type === "language") return [key, value || null]
      return [key, value.trim() || null]
    }),
  )

const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

// Edits series details. Admins save straight away (written into the files in the background);
// everyone else sends a suggestion for an admin to approve.
export function MetadataDialog({ manga, isAdmin, onClose, onSaved }) {
  const s = useStyles()
  // A pending suggestion starts from what the user suggested last time
  const [form, setForm] = useState(() =>
    toForm({ ...manga.metadata, ...(manga.my_suggestion?.changes ?? {}) }),
  )
  const [saving, setSaving] = useState(false)
  const [progress, setProgress] = useState(null)

  const set = (key, value) => setForm((previous) => ({ ...previous, [key]: value }))

  const submit = async (event) => {
    event.preventDefault()
    const values = fromForm(form)
    if (values.year !== null && (!Number.isInteger(values.year) || values.year < 1000 || values.year > 9999)) {
      toast.error("Year must be a four-digit number")
      return
    }
    const changes = Object.fromEntries(
      Object.entries(values).filter(([key, value]) => !same(value, manga.metadata[key])),
    )
    if (!Object.keys(changes).length) {
      toast.info("Nothing changed")
      return
    }

    setSaving(true)
    try {
      if (isAdmin) {
        const { job } = await api.editManga(manga.id, { metadata: changes })
        onSaved()
        if (job) {
          const done = await waitForJob(job, setProgress)
          toast.success(done.message ? `Saved. ${done.message}.` : "Saved")
        } else {
          toast.success("Saved")
        }
      } else {
        await api.suggestMetadata(manga.id, changes)
        toast.success("Suggestion sent. An admin will review it.")
        onSaved()
      }
      onClose()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setSaving(false)
      setProgress(null)
    }
  }

  const withdraw = async () => {
    setSaving(true)
    try {
      await api.withdrawSuggestion(manga.id)
      toast.success("Suggestion withdrawn")
      onSaved()
      onClose()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="metadata-title"
        onSubmit={submit}
        className={`w-full sm:max-w-lg max-h-[90vh] flex flex-col rounded-t-lg sm:rounded-lg border pb-[env(safe-area-inset-bottom)] ${
          s.dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
        }`}
      >
        <div className="p-5 pb-3">
          <h2 id="metadata-title" className={s.dark ? "text-white" : "text-gray-900"}>
            {isAdmin ? "Edit details" : "Suggest changes"}
          </h2>
          <p className={`text-sm mt-1 ${s.muted}`}>
            {isAdmin
              ? "Changes are saved now and written into the series' files (ComicInfo.xml)."
              : "An admin reviews your suggestion before it changes anything."}
          </p>
        </div>

        <div className="px-5 overflow-y-auto space-y-4">
          {METADATA_FIELDS.map((field) => {
            const id = `metadata-${field.key}`
            return (
              <div key={field.key}>
                <label htmlFor={id} className={`block text-sm mb-1 ${s.text}`}>
                  {field.label}
                  {field.hint && <span className={`ml-2 font-normal ${s.muted}`}>{field.hint}</span>}
                </label>
                {field.type === "textarea" ? (
                  <textarea
                    id={id}
                    rows={5}
                    maxLength={field.max}
                    value={form[field.key]}
                    onChange={(event) => set(field.key, event.target.value)}
                    className={`${s.input} w-full`}
                  />
                ) : field.type === "direction" ? (
                  <select
                    id={id}
                    value={form[field.key]}
                    onChange={(event) => set(field.key, event.target.value)}
                    className={`${s.input} w-full`}
                  >
                    <option value="">Not set (use the reader setting)</option>
                    <option value="rtl">Right to left (Japanese manga)</option>
                    <option value="ltr">Left to right</option>
                  </select>
                ) : field.type === "language" ? (
                  <select
                    id={id}
                    value={form[field.key]}
                    onChange={(event) => set(field.key, event.target.value)}
                    className={`${s.input} w-full`}
                  >
                    <option value="">Not set</option>
                    {LANGUAGES.map((language) => (
                      <option key={language.code} value={language.code}>
                        {language.name}
                      </option>
                    ))}
                    {/* A value from before the list was fixed stays selectable until it's changed */}
                    {form[field.key] && !LANGUAGES.some((language) => language.code === form[field.key]) && (
                      <option value={form[field.key]}>{form[field.key]}</option>
                    )}
                  </select>
                ) : (
                  <input
                    id={id}
                    type="text"
                    inputMode={field.type === "year" ? "numeric" : undefined}
                    maxLength={field.type === "year" ? 4 : field.max}
                    value={form[field.key]}
                    onChange={(event) => set(field.key, event.target.value)}
                    className={`${s.input} w-full`}
                  />
                )}
              </div>
            )
          })}
        </div>

        <div className="p-5 pt-4 space-y-3">
          {progress && progress.total > 0 && (
            <p className={`text-sm ${s.muted}`}>
              Writing files: {progress.done} of {progress.total}…
            </p>
          )}
          <div className="flex flex-wrap gap-3 justify-end">
            {!isAdmin && manga.my_suggestion && (
              <button type="button" className={`${s.dangerButton} mr-auto`} disabled={saving} onClick={withdraw}>
                Withdraw
              </button>
            )}
            <button type="button" className={s.button} disabled={saving} onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className={s.primaryButton} disabled={saving}>
              {saving ? "Saving…" : isAdmin ? "Save" : "Send suggestion"}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
