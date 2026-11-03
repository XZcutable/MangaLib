import { useSearchParams } from "react-router"
import { MangaSection } from "../components/MangaSection"
import { useMangaList } from "../hooks/useMangaList"
import { useTheme } from "../context/ThemeContext"

export function Search() {
  const [params] = useSearchParams()
  const q = params.get("q") ?? ""
  const { theme } = useTheme()
  const results = useMangaList(null, { q })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <MangaSection
        title={q ? `Results for "${q}"` : "Search"}
        list={results}
        infinite
        emptyMessage={q ? "No manga matched your search." : "Type in the search bar to find manga."}
      />
      <p className={`text-sm ${theme === "dark" ? "text-gray-500" : "text-gray-500"}`}>
        Tips: <code>tag:action</code> includes a tag, <code>!tag:romance</code> excludes one,{" "}
        <code>tag:unread</code>, <code>tag:progress</code> and <code>tag:nsfw</code> filter by status.
      </p>
    </div>
  )
}
