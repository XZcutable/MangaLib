import { Link } from "react-router"
import { BookCheck, Heart, Star } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { ImageWithFallback } from "./ImageWithFallback"
import { useTheme } from "../context/ThemeContext"
import { useAuth } from "../context/AuthContext"
import { imageUrl, parseServerDate } from "../lib/api"

export function MangaCard({ manga, showProgress = false, showUpdated = false }) {
  const { theme } = useTheme()
  const { serverInfo } = useAuth()
  const user = manga.user
  // Early pages of a long series round to 0%, so any progress shows a sliver
  const percent = manga.progress > 0 ? Math.max(2, Math.round(manga.progress * 100)) : 0
  const hideTitle = serverInfo?.hide_titles

  return (
    <Link to={`/manga/${manga.id}`} className="group block" title={manga.title}>
      <div className="relative aspect-[2/3] rounded-lg overflow-hidden mb-3 bg-gray-200">
        <ImageWithFallback
          src={imageUrl(manga.cover_url)}
          alt={manga.title}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        />
        {showProgress && percent > 0 && (
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
            <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
              <div
                className="bg-brand-500 h-2 rounded-full"
                style={{ width: `${percent}%` }}
              />
            </div>
            {user && (
              <p className="text-white text-sm">
                {user.is_read
                  ? "Finished"
                  : `Chapter ${user.current_chapter} of ${manga.total_chapters}`}
              </p>
            )}
          </div>
        )}
        {manga.rating?.count > 0 && (
          <span
            className="absolute top-2 left-2 inline-flex items-center gap-0.5 bg-black/70 text-white text-xs px-1.5 py-0.5 rounded"
            aria-label={`Average score ${manga.rating.average.toFixed(1)} out of 10`}
          >
            <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
            {manga.rating.average.toFixed(1)}
          </span>
        )}
        <div className="absolute top-2 right-2 flex gap-1">
          {user?.is_favorite && (
            <span className="bg-black/70 text-white p-1 rounded" aria-label="Favorite">
              <Heart className="w-3.5 h-3.5 fill-heart text-heart" />
            </span>
          )}
          {user?.is_read && !showProgress && (
            <span className="bg-black/70 text-white p-1 rounded" aria-label="Read">
              <BookCheck className="w-3.5 h-3.5" />
            </span>
          )}
        </div>
      </div>

      <div className="space-y-1">
        {!hideTitle && (
          <h3
            className={`font-semibold line-clamp-2 group-hover:text-brand-400 transition-colors ${
              theme === "dark" ? "text-gray-100" : "text-gray-900"
            }`}
          >
            {manga.title}
          </h3>
        )}
        <div
          className={`text-sm ${theme === "dark" ? "text-gray-400" : "text-gray-600"}`}
        >
          {manga.release_year && `${manga.release_year} • `}
          {manga.total_chapters} {manga.total_chapters === 1 ? "chapter" : "chapters"}
        </div>
        {showUpdated && manga.last_updated && (
          <div className="text-xs text-brand-500">
            Updated {formatDistanceToNow(parseServerDate(manga.last_updated), { addSuffix: true })}
          </div>
        )}
      </div>
    </Link>
  )
}
