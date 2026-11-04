import { useEffect, useRef } from "react"
import { Link } from "react-router"
import { MangaCard } from "./MangaCard"
import { StatusMessage } from "./StatusMessage"
import { useTheme } from "../context/ThemeContext"

// A titled grid of manga. Pass `list` (from useMangaList) to get loading, errors,
// an empty message and, with `infinite`, more results as you scroll.
export function MangaSection({
  title,
  description,
  list,
  manga,
  showProgress = false,
  showUpdated = false,
  infinite = false,
  emptyMessage = "Nothing here yet.",
  seeAllPath,
  hideWhenEmpty = false,
}) {
  const { theme } = useTheme()
  const items = manga ?? list?.items ?? []
  const sentinelRef = useRef(null)

  useEffect(() => {
    if (!infinite || !list?.hasMore || !sentinelRef.current) return
    const observer = new IntersectionObserver(
      (entries) => entries[0].isIntersecting && list.loadMore(),
      { rootMargin: "600px" },
    )
    observer.observe(sentinelRef.current)
    return () => observer.disconnect()
  }, [infinite, list])

  const isEmpty = list && !list.loading && !list.error && items.length === 0
  if (hideWhenEmpty && isEmpty) return null

  return (
    <section className="mb-12">
      <div className={`flex items-baseline justify-between gap-4 ${description ? "mb-1" : "mb-6"}`}>
        <h2 className={theme === "dark" ? "text-white" : "text-gray-900"}>
          {title}
          {list?.total > 0 && infinite && (
            <span
              className={`ml-2 text-sm font-normal ${
                theme === "dark" ? "text-gray-500" : "text-gray-500"
              }`}
            >
              {list.total}
            </span>
          )}
        </h2>
        {seeAllPath && items.length > 0 && (
          <Link to={seeAllPath} className="text-sm text-brand-500 hover:text-brand-400">
            See all
          </Link>
        )}
      </div>

      {description && (
        <p className={`text-sm mb-6 ${theme === "dark" ? "text-gray-400" : "text-gray-600"}`}>
          {description}
        </p>
      )}
      {list?.error && items.length === 0 ? (
        <StatusMessage message={list.error.message} onRetry={list.reload} />
      ) : isEmpty ? (
        <StatusMessage message={emptyMessage} />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-6">
          {items.map((item) => (
            <MangaCard
              key={item.id}
              manga={item}
              showProgress={showProgress}
              showUpdated={showUpdated}
            />
          ))}
          {list?.loading &&
            Array.from({ length: items.length ? 5 : 10 }, (_, index) => (
              <div key={`loading-${index}`} className="animate-pulse">
                <div
                  className={`aspect-[2/3] rounded-lg mb-3 ${
                    theme === "dark" ? "bg-gray-800" : "bg-gray-200"
                  }`}
                />
                <div
                  className={`h-4 rounded w-3/4 ${
                    theme === "dark" ? "bg-gray-800" : "bg-gray-200"
                  }`}
                />
              </div>
            ))}
        </div>
      )}
      {infinite && list?.hasMore && <div ref={sentinelRef} className="h-1" />}
      {infinite && list?.error && items.length > 0 && (
        <StatusMessage message={list.error.message} onRetry={list.loadMore} />
      )}
    </section>
  )
}
