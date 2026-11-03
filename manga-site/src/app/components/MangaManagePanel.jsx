import { useEffect, useState } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"
import { useAuth } from "../context/AuthContext"
import { useStyles } from "../hooks/useStyles"
import { api } from "../lib/api"

// Admin tools on the manga page: rename and tags. The owner also gets rescan, folder location and remove.
export function MangaManagePanel({ manga, onChanged }) {
  const s = useStyles()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [title, setTitle] = useState(manga.title)
  const [allTags, setAllTags] = useState(null)
  const [selected, setSelected] = useState(() => new Set(manga.tags.map((tag) => tag.tag)))
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.tags().then(({ tags }) => setAllTags(tags)).catch(() => setAllTags([]))
  }, [])

  useEffect(() => {
    setTitle(manga.title)
    setSelected(new Set(manga.tags.map((tag) => tag.tag)))
  }, [manga])

  const run = async (action, success) => {
    setBusy(true)
    try {
      await action()
      if (success) toast.success(success)
      onChanged()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setBusy(false)
    }
  }

  const toggleTag = (tag) => {
    const next = new Set(selected)
    next.has(tag) ? next.delete(tag) : next.add(tag)
    setSelected(next)
  }

  const tagsChanged =
    selected.size !== manga.tags.length || manga.tags.some((tag) => !selected.has(tag.tag))

  const remove = () => {
    const message = `Remove "${manga.title}" from the library? Files on the server aren't deleted, so the next scan adds it back unless you move them.`
    if (!confirm(message)) return
    setBusy(true)
    api
      .deleteManga(manga.id)
      .then(() => {
        toast.success("Removed from the library")
        navigate("/", { replace: true })
      })
      .catch((error) => {
        toast.error(error.message)
        setBusy(false)
      })
  }

  return (
    <details className={`${s.card} group`}>
      <summary className={`cursor-pointer select-none ${s.dark ? "text-white" : "text-gray-900"}`}>
        Manage
      </summary>

      <div className="mt-6 space-y-8">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            run(() => api.editManga(manga.id, { title }), "Title saved")
          }}
        >
          <h3 className={s.subheading}>Title</h3>
          <input
            className={`${s.input} w-full`}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
          />
          <div className="flex flex-wrap items-center gap-3">
            <button className={s.button} disabled={busy || !title.trim() || title === manga.title}>
              Save title
            </button>
            {manga.title !== manga.original_title && (
              <button
                type="button"
                className={s.button}
                disabled={busy}
                onClick={() => run(() => api.editManga(manga.id, { title: null }), "Title reset")}
              >
                Reset to "{manga.original_title}"
              </button>
            )}
          </div>
        </form>

        <div className="space-y-3">
          <h3 className={s.subheading}>Tags</h3>
          {allTags === null ? (
            <p className={s.muted}>Loading…</p>
          ) : allTags.length === 0 ? (
            <p className={`text-sm ${s.muted}`}>No tags exist yet. Create them in Settings → Tags.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {allTags.map((tag) => (
                <button
                  key={tag.tag}
                  type="button"
                  className={s.chip(selected.has(tag.tag))}
                  onClick={() => toggleTag(tag.tag)}
                  aria-pressed={selected.has(tag.tag)}
                >
                  {tag.tag}
                  {tag.nsfw && <span className="ml-1 text-red-400">•</span>}
                </button>
              ))}
            </div>
          )}
          <button
            className={s.button}
            disabled={busy || !tagsChanged}
            onClick={() => run(() => api.setMangaTags(manga.id, [...selected]), "Tags saved")}
          >
            Save tags
          </button>
        </div>

        {user?.is_owner && (
          <div className="space-y-3">
            <h3 className={s.subheading}>Files</h3>
            {manga.path && (
              <p className={`text-sm font-mono break-all ${s.muted}`}>{manga.path}</p>
            )}
            <div className="flex flex-wrap gap-3">
              <button
                className={s.button}
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const { total_chapters } = await api.rescanManga(manga.id)
                    toast.success(`Rescanned: ${total_chapters} chapters`)
                  })
                }
              >
                Rescan files
              </button>
              <button className={s.dangerButton} disabled={busy} onClick={remove}>
                Remove from library
              </button>
            </div>
          </div>
        )}
      </div>
    </details>
  )
}
