import { useCallback, useEffect, useState } from "react"
import { useAuth } from "../context/AuthContext"
import { api } from "../lib/api"
import { LANGUAGES } from "../lib/languages"
import { STATUSES } from "../lib/searchSyntax"

// Tags per server address, refreshed at most once a minute
const tagCache = new Map()
const TAG_MAX_AGE = 60 * 1000

function loadTags(server) {
  const cached = tagCache.get(server)
  if (cached && Date.now() - cached.loaded < TAG_MAX_AGE) return cached.promise
  const promise = api
    .tags()
    .then((response) => response.tags ?? [])
    .catch(() => {
      tagCache.delete(server)
      return []
    })
  tagCache.set(server, { promise, loaded: Date.now() })
  return promise
}

// The value lists the search box suggests from. Tags load the first time `load()` is called.
export function useSearchSuggestions(enabled) {
  const { server, serverInfo } = useAuth()
  const [tags, setTags] = useState([])

  const load = useCallback(() => {
    if (!enabled) return
    loadTags(server ?? "").then(setTags)
  }, [enabled, server])

  useEffect(() => setTags([]), [server])

  const languages = serverInfo?.languages ?? LANGUAGES
  return {
    load,
    sources: {
      tags: tags.filter((tag) => !tag.nsfw).map((tag) => ({ value: tag.tag })),
      nsfwTags: tags.filter((tag) => tag.nsfw).map((tag) => ({ value: tag.tag })),
      languages: languages.map((language) => ({ value: language.name.toLowerCase(), label: language.name })),
      statuses: STATUSES.map((status) => ({ value: status.value, detail: status.label })),
    },
  }
}
