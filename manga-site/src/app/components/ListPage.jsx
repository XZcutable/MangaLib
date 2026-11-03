import { MangaSection } from "./MangaSection"
import { useMangaList } from "../hooks/useMangaList"

// A full page for one server list, loading more as you scroll
export function ListPage({ title, list, sort, showProgress = false, emptyMessage }) {
  const results = useMangaList(list, { sort })
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <MangaSection
        title={title}
        list={results}
        showProgress={showProgress}
        emptyMessage={emptyMessage}
        infinite
      />
    </div>
  )
}
