import { useEffect, useState } from "react"
import { Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"

const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`

// Owner only: old page images a crunch packed into a .cbz but couldn't delete (usually because the file
// was in use). Shown only while there are some. `count` comes from GET /library; `reloadKey` changes
// when a crunch finishes, so new leftovers show up.
export function LeftoverFiles({ count, reloadKey }) {
  const s = useStyles()
  const [files, setFiles] = useState(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!count && reloadKey === 0) return
    api
      .leftoverFiles()
      .then(({ files }) => setFiles(files))
      .catch(() => {})
  }, [count, reloadKey])

  const retry = async () => {
    setDeleting(true)
    try {
      const result = await api.deleteLeftoverFiles()
      setFiles(result.files)
      const parts = []
      if (result.deleted) parts.push(`Deleted ${plural(result.deleted, "file")}`)
      if (result.kept)
        parts.push(`kept ${plural(result.kept, "file")} whose .cbz is gone, so they'll be scanned again`)
      if (result.files.length) parts.push(`${plural(result.files.length, "file")} still couldn't be deleted`)
      const message = parts.join("; ") || "Nothing to delete"
      result.files.length ? toast.warning(message) : toast.success(message)
    } catch (error) {
      toast.error(error.message)
    } finally {
      setDeleting(false)
    }
  }

  if (!files?.length) return null
  return (
    <div className="mt-6">
      <h3 className={s.subheading}>Files waiting to be deleted</h3>
      <p className={`text-sm mb-3 ${s.muted}`}>
        These old page images were packed into a .cbz, but couldn't be deleted at the time, usually because
        someone was reading them. They're already in the .cbz and are left out of scans. Deleting them again
        is safe; a file whose .cbz has gone missing is kept.
      </p>
      <ul className={`max-h-60 overflow-y-auto border rounded-md divide-y mb-3 ${s.divider}`}>
        {files.map((file) => (
          <li key={file.id} className="px-3 py-2 text-sm">
            <span className={`block truncate font-mono ${s.text}`} title={file.path}>
              {file.path}
            </span>
            <span className={`block truncate ${s.muted}`} title={file.error}>
              {file.manga_title}
              {file.error ? ` · ${file.error}` : ""}
            </span>
          </li>
        ))}
      </ul>
      <button className={s.dangerButton} onClick={retry} disabled={deleting}>
        <span className="inline-flex items-center gap-2">
          <Trash2 className="w-4 h-4" />
          {deleting ? "Deleting…" : `Delete ${plural(files.length, "file")}`}
        </span>
      </button>
    </div>
  )
}
