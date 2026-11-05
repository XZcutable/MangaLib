import { useEffect, useState } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"
import { useAuth } from "../context/AuthContext"
import { useStyles } from "../hooks/useStyles"
import { api } from "../lib/api"
import { useServerFeatures } from "../lib/features"
import { waitForJob } from "../lib/metadata"

// Admin tools on the manga page: rename and tags. The owner also gets rescan, moving, converting and remove.
export function MangaManagePanel({ manga, onChanged }) {
  const s = useStyles()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [title, setTitle] = useState(manga.title)
  const [allTags, setAllTags] = useState(null)
  const [selected, setSelected] = useState(() => new Set(manga.tags.map((tag) => tag.tag)))
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState(null) // a crunch, unpack or move in progress
  const features = useServerFeatures()
  const [folders, setFolders] = useState(null) // library folders, for moving the series
  const [target, setTarget] = useState("")

  useEffect(() => {
    api.tags().then(({ tags }) => setAllTags(tags)).catch(() => setAllTags([]))
  }, [])

  const canMove = user?.is_owner && features.moveFiles
  useEffect(() => {
    if (canMove) api.library().then(({ paths }) => setFolders(paths)).catch(() => setFolders([]))
  }, [canMove])
  // The library folder the series is in now; the others are where it can move to
  const storedPath = manga.path?.replace(/\\/g, "/") ?? ""
  const currentFolder = folders?.find((folder) => storedPath.startsWith(folder.endsWith("/") ? folder : `${folder}/`))
  const otherFolders = folders?.filter((folder) => folder !== currentFolder) ?? []
  const otherKey = otherFolders.join("\n")
  useEffect(() => {
    if (!otherFolders.includes(target)) setTarget(otherFolders[0] ?? "")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [otherKey])

  const moveFiles = async () => {
    const message = `Move the files of "${manga.title}" to ${target}? Reading progress, scores and read marks carry over. Copying to another disk can take a while.`
    if (!confirm(message)) return
    try {
      const { job: started } = await api.moveManga(manga.id, target)
      follow(started)
    } catch (error) {
      toast.error(error.message)
    }
  }

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

  // Follow a conversion started here or already running when the page opened
  useEffect(() => {
    const running = manga.repack?.job
    if (running && !job) follow(running)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manga.repack?.job?.id])

  const follow = async (started) => {
    setJob(started)
    try {
      const done = await waitForJob(started, setJob)
      toast.success(done.message ?? "Done")
    } catch (error) {
      toast.error(error.message)
    } finally {
      setJob(null)
      onChanged()
    }
  }

  const convert = async (kind) => {
    const count = kind === "crunch" ? manga.repack.crunchable : manga.repack.unpackable
    const what = count === 1 ? "chapter" : "chapters"
    const message =
      kind === "crunch"
        ? `Pack ${count} image-folder ${what} into .cbz files? Each folder's images are deleted once its .cbz has been written and checked. Other files in the folders are kept.`
        : `Unpack ${count} ${what} into folders of images? Each .cbz/.zip is deleted once its pages have been extracted and checked.`
    if (!confirm(message)) return
    try {
      const { job: started } =
        kind === "crunch" ? await api.crunchManga(manga.id) : await api.unpackManga(manga.id)
      follow(started)
    } catch (error) {
      toast.error(error.message)
    }
  }

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
              <button className={s.dangerButton} disabled={busy || job} onClick={remove}>
                Remove from library
              </button>
            </div>

            {job && (
              <div>
                <div className={`h-2 rounded-full overflow-hidden ${s.dark ? "bg-gray-800" : "bg-gray-200"}`}>
                  <div
                    className={`h-full bg-brand-600 transition-[width] ${job.total ? "" : "w-1/3 animate-pulse"}`}
                    style={job.total ? { width: `${Math.round((job.done / job.total) * 100)}%` } : undefined}
                  />
                </div>
                <p className={`text-xs mt-1 ${s.muted}`}>
                  {{ crunch: "Crunching", unpack: "Unpacking", move: "Moving" }[job.kind] ?? "Working"}
                  {job.total ? ` ${job.done} of ${job.total}` : ""}…
                </p>
              </div>
            )}

            {canMove && otherFolders.length > 0 && (
              <div className="pt-2 space-y-3">
                <h3 className={s.subheading}>Move to another folder</h3>
                <div className="flex flex-wrap gap-2">
                  <select
                    className={`${s.input} flex-1 min-w-0 font-mono text-sm`}
                    value={target}
                    onChange={(event) => setTarget(event.target.value)}
                    aria-label="Library folder to move to"
                  >
                    {otherFolders.map((folder) => (
                      <option key={folder} value={folder}>
                        {folder}
                      </option>
                    ))}
                  </select>
                  <button className={s.button} disabled={busy || job || !target} onClick={moveFiles}>
                    Move
                  </button>
                </div>
              </div>
            )}

            {manga.repack && (
              <div className="pt-2 space-y-3">
                <h3 className={s.subheading}>Convert</h3>
                <p className={`text-sm ${s.muted}`}>
                  Crunch packs folders of page images into .cbz files. Unpack does the opposite. Reading
                  progress, scores and read marks carry over.
                </p>
                {!job && (
                  <div className="flex flex-wrap gap-3">
                    <button
                      className={s.button}
                      disabled={busy || !manga.repack.crunchable}
                      onClick={() => convert("crunch")}
                      title={manga.repack.crunchable ? undefined : "No image-folder chapters"}
                    >
                      Crunch to .cbz{manga.repack.crunchable ? ` (${manga.repack.crunchable})` : ""}
                    </button>
                    <button
                      className={s.button}
                      disabled={busy || !manga.repack.unpackable}
                      onClick={() => convert("unpack")}
                      title={manga.repack.unpackable ? undefined : "No .cbz or .zip chapters"}
                    >
                      Unpack to folders{manga.repack.unpackable ? ` (${manga.repack.unpackable})` : ""}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </details>
  )
}
