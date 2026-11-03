import { useCallback, useEffect, useState } from "react"
import { X } from "lucide-react"
import { toast } from "sonner"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"

// Admin: the tags that can be put on manga. NSFW tags are marked in red.
export function TagsSection() {
  const s = useStyles()
  const [tags, setTags] = useState(null)
  const [name, setName] = useState("")
  const [nsfw, setNsfw] = useState(false)

  const load = useCallback(() => {
    api.tags().then(({ tags }) => setTags(tags)).catch((error) => toast.error(error.message))
  }, [])
  useEffect(load, [load])

  const add = async (event) => {
    event.preventDefault()
    try {
      await api.createTag(name, nsfw)
      setName("")
      load()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const remove = async (tag) => {
    if (!confirm(`Delete the tag "${tag}"? It's removed from every manga that has it.`)) return
    try {
      await api.deleteTag(tag)
      load()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <section className={s.card}>
      <h2 className={s.heading}>Tags</h2>
      <form onSubmit={add} className="flex flex-wrap items-center gap-2 mb-4">
        <input
          className={`${s.input} flex-1 min-w-[12rem]`}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="New tag, e.g. slice of life"
          required
        />
        <label className={`flex items-center gap-2 text-sm ${s.muted}`}>
          <input type="checkbox" checked={nsfw} onChange={(event) => setNsfw(event.target.checked)} />
          NSFW
        </label>
        <button className={s.button}>Add tag</button>
      </form>
      <p className={`text-xs mb-4 ${s.muted}`}>
        Lowercase words separated by spaces. Adding an existing tag with the other NSFW setting
        switches it.
      </p>

      {tags === null ? (
        <p className={s.muted}>Loading…</p>
      ) : tags.length === 0 ? (
        <p className={s.muted}>No tags yet.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <span
              key={tag.tag}
              className={`inline-flex items-center gap-1 text-sm pl-3 pr-1 py-1 rounded-full ${
                tag.nsfw
                  ? "bg-red-900/40 text-red-300"
                  : s.dark
                    ? "bg-gray-800 text-gray-300"
                    : "bg-gray-200 text-gray-700"
              }`}
            >
              {tag.tag}
              <button
                onClick={() => remove(tag.tag)}
                className="p-0.5 rounded-full hover:bg-black/20"
                aria-label={`Delete tag ${tag.tag}`}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
    </section>
  )
}
