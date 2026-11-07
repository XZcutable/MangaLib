import { useSearchParams } from "react-router"
import { MangaSection } from "../components/MangaSection"
import { useMangaList } from "../hooks/useMangaList"
import { useTheme } from "../context/ThemeContext"
import { useServerFeatures } from "../lib/features"

const TIPS = [
  ["tag:fantasy|action", "either tag"],
  ["tag:fantasy&action", "both tags"],
  ['tag:"slice of life"', "tags with spaces"],
  ["nsfw:gore", "NSFW tags"],
  ["language:english|japanese", "language"],
  ["is:unread", "also read, progress"],
  ['"exact phrase"', "title text"],
  ["-tag:romance", "a leading - excludes"],
  ["-nsfw", "hide all NSFW"],
]

export function Search() {
  const [params] = useSearchParams()
  const q = params.get("q") ?? ""
  const { theme } = useTheme()
  const { searchSyntax } = useServerFeatures()
  const results = useMangaList(null, { q })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <MangaSection
        title={q ? `Results for "${q}"` : "Search"}
        list={results}
        infinite
        emptyPose="searching"
        emptyMessage={q ? "No manga matched your search." : "Type in the search bar to find manga."}
      />
      {searchSyntax ? (
        <div className="text-sm text-gray-500">
          <p className="mb-2">Search tips (suggestions appear as you type):</p>
          <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
            {TIPS.map(([example, meaning]) => (
              <li key={example}>
                <code className={theme === "dark" ? "text-gray-300" : "text-gray-700"}>{example}</code> {meaning}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-gray-500">
          Tips: <code>tag:action</code> includes a tag, <code>!tag:romance</code> excludes one,{" "}
          <code>tag:unread</code>, <code>tag:progress</code> and <code>tag:nsfw</code> filter by status.
        </p>
      )}
    </div>
  )
}
