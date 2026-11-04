import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowUp, Folder, X } from "lucide-react"
import { useStyles } from "../../hooks/useStyles"
import { api } from "../../lib/api"

// Browse the server's folders and pick one. Folders shown are on the server, not this device.
export function FolderPicker({ onPick, onClose }) {
  const s = useStyles()
  const [listing, setListing] = useState(null)
  const [typed, setTyped] = useState("")
  const [error, setError] = useState(null)

  // Only the most recent request may update the list, so a slow earlier one can't overwrite it
  const latestRequest = useRef(0)
  // Counts edits to the path box, so a response never replaces something typed while it loaded
  const edits = useRef(0)
  const open = useCallback(async (dir) => {
    const request = ++latestRequest.current
    const editsAtStart = edits.current
    setError(null)
    try {
      const result = await api.browseFolders(dir)
      if (request !== latestRequest.current) return
      setListing(result)
      if (edits.current === editsAtStart) setTyped(result.dir)
    } catch (error) {
      if (request === latestRequest.current) setError(error.message)
    }
  }, [])

  useEffect(() => {
    open("")
  }, [open])

  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[60] bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Choose a folder"
        onClick={(event) => event.stopPropagation()}
        className={`w-full sm:max-w-lg max-h-[85vh] flex flex-col rounded-t-lg sm:rounded-lg border ${
          s.dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
        }`}
      >
        <div className="flex items-center justify-between p-4 pb-2">
          <h2 className={s.dark ? "text-white" : "text-gray-900"}>Choose a folder on the server</h2>
          <button onClick={onClose} className={`p-1 ${s.muted}`} aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form
          className="flex gap-2 px-4 pb-3"
          onSubmit={(event) => {
            event.preventDefault()
            open(typed)
          }}
        >
          <input
            className={`${s.input} flex-1 min-w-0`}
            value={typed}
            onChange={(event) => {
              edits.current++
              setTyped(event.target.value)
            }}
            placeholder="/mnt/manga or D:/Manga"
            autoCapitalize="none"
            autoCorrect="off"
          />
          <button className={s.button}>Go</button>
        </form>
        {error && <p className="px-4 pb-2 text-sm text-red-500">{error}</p>}

        <ul className={`flex-1 overflow-y-auto border-y divide-y ${s.divider}`}>
          {listing?.parent !== null && listing?.parent !== undefined && (
            <li>
              <button
                onClick={() => open(listing.parent)}
                className={`w-full flex items-center gap-3 px-4 py-2 text-left ${s.muted} hover:bg-brand-600/10`}
              >
                <ArrowUp className="w-4 h-4" /> Up
              </button>
            </li>
          )}
          {listing?.folders.map((folder) => (
            <li key={folder.path}>
              <button
                onClick={() => open(folder.path)}
                className={`w-full flex items-center gap-3 px-4 py-2 text-left hover:bg-brand-600/10 ${s.text}`}
              >
                <Folder className="w-4 h-4 text-brand-500 shrink-0" />
                <span className="truncate">{folder.name}</span>
              </button>
            </li>
          ))}
          {listing && listing.folders.length === 0 && (
            <li className={`px-4 py-3 text-sm ${s.muted}`}>No folders inside this one.</li>
          )}
        </ul>

        <div className="flex items-center justify-between gap-3 p-4">
          <p className={`text-sm truncate ${s.muted}`}>{listing?.dir || "Pick a drive or folder"}</p>
          <button
            className={s.primaryButton}
            disabled={!listing?.dir}
            onClick={() => onPick(listing.dir)}
          >
            Use this folder
          </button>
        </div>
      </div>
    </div>
  )
}
