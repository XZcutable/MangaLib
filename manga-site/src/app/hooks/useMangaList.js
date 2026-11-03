import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "../lib/api"

// Loads a manga list (or search results when `q` is given) in batches.
// loadMore() fetches the next batch. hasMore is false once everything is loaded.
export function useMangaList(list, { q, limit, sort } = {}) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(null)
  const [nextOffset, setNextOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const controllerRef = useRef(null)
  const loadingRef = useRef(false)

  const fetchBatch = useCallback(
    async (offset, replace) => {
      controllerRef.current?.abort()
      const controller = new AbortController()
      controllerRef.current = controller
      loadingRef.current = true
      setLoading(true)
      setError(null)
      try {
        const options = { offset, limit, sort }
        const page =
          q !== undefined
            ? await api.search(q, options, controller.signal)
            : await api.list(list, options, controller.signal)
        setItems((previous) => {
          if (replace) return page.items
          // A shuffled list can repeat ids across batches
          const seen = new Set(previous.map((item) => item.id))
          return [...previous, ...page.items.filter((item) => !seen.has(item.id))]
        })
        setTotal(page.total)
        setNextOffset(page.next_offset)
      } catch (error) {
        if (error.name !== "AbortError") setError(error)
      } finally {
        if (controllerRef.current === controller) {
          loadingRef.current = false
          setLoading(false)
        }
      }
    },
    [list, q, limit, sort],
  )

  useEffect(() => {
    setItems([])
    setTotal(null)
    fetchBatch(0, true)
    return () => controllerRef.current?.abort()
  }, [fetchBatch])

  const loadMore = useCallback(() => {
    if (!loadingRef.current && nextOffset !== null) fetchBatch(nextOffset, false)
  }, [fetchBatch, nextOffset])

  const reload = useCallback(() => fetchBatch(0, true), [fetchBatch])

  return { items, total, loading, error, hasMore: nextOffset !== null, loadMore, reload }
}
