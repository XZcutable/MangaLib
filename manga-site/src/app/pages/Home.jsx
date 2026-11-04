import { MangaSection } from "../components/MangaSection"
import { useMangaList } from "../hooks/useMangaList"
import { useServerFeatures } from "../lib/features"

export function Home() {
  const history = useMangaList("history", { limit: 10 })
  const queued = useMangaList("queued", { limit: 10 })
  const discover = useMangaList("random", { limit: 15 })
  const { ratings } = useServerFeatures()
  // An older server has no "rated" list; asking for it would show an error
  const rated = useMangaList(ratings ? "rated" : "favorites", { limit: 10 })
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <MangaSection
        title="Jump back in"
        list={history}
        showProgress
        seeAllPath="/history"
        hideWhenEmpty
      />
      <MangaSection title="Your next read" list={queued} seeAllPath="/bookmarks" hideWhenEmpty />
      {ratings && <MangaSection title="Top rated" list={rated} seeAllPath="/top-rated" hideWhenEmpty />}
      <MangaSection
        title="Discover"
        list={discover}
        seeAllPath="/random"
        emptyMessage="Your library is empty. Add a manga folder in the server settings and scan it."
      />
    </div>
  )
}
