import { useState } from "react"
import { useNavigate } from "react-router"
import { Shuffle } from "lucide-react"
import { MangaSection } from "../components/MangaSection"
import { useMangaList } from "../hooks/useMangaList"
import { api } from "../lib/api"
import { toast } from "sonner"

export function Random() {
  const navigate = useNavigate()
  const list = useMangaList("random")
  const [picking, setPicking] = useState(false)

  const surprise = async (unread) => {
    setPicking(true)
    try {
      const { id } = await api.random(unread)
      navigate(`/manga/${id}`)
    } catch (error) {
      toast.error(error.message)
    } finally {
      setPicking(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-wrap gap-3 mb-8">
        <button
          onClick={() => surprise(true)}
          disabled={picking}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-60 transition-colors"
        >
          <Shuffle className="w-4 h-4" /> Random unread
        </button>
        <button
          onClick={() => surprise(false)}
          disabled={picking}
          className="inline-flex items-center gap-2 px-4 py-2 border border-blue-600 text-blue-500 rounded-md hover:bg-blue-600/10 disabled:opacity-60 transition-colors"
        >
          <Shuffle className="w-4 h-4" /> Anything
        </button>
        <button
          onClick={list.reload}
          className="px-4 py-2 text-blue-500 rounded-md hover:bg-blue-600/10 transition-colors"
        >
          Shuffle again
        </button>
      </div>
      <MangaSection title="Random Selection" list={list} infinite />
    </div>
  )
}
