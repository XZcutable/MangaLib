import { Star } from "lucide-react"
import { useTheme } from "../context/ThemeContext"

// A 1–10 score as ten segments. Tapping your current score again clears it.
export function RatingPicker({ rating, onChange, disabled = false }) {
  const { theme } = useTheme()
  const dark = theme === "dark"
  const mine = rating?.mine ?? null
  const muted = dark ? "text-gray-400" : "text-gray-600"

  return (
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-2">
        <span className={`text-sm ${muted}`}>Your score</span>
        <span className={`text-sm font-medium ${dark ? "text-white" : "text-gray-900"}`}>
          {mine === null ? "Not rated" : `${mine}/10`}
        </span>
        {rating?.count > 0 && (
          <span className={`inline-flex items-center gap-1 text-sm ${muted}`}>
            <Star className="w-3.5 h-3.5 fill-current text-amber-400" />
            {rating.average.toFixed(1)} average from {rating.count}{" "}
            {rating.count === 1 ? "rating" : "ratings"}
          </span>
        )}
      </div>
      <div className="flex gap-1 max-w-sm" role="radiogroup" aria-label="Your score out of 10">
        {Array.from({ length: 10 }, (_, index) => {
          const value = index + 1
          const filled = mine !== null && value <= mine
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={mine === value}
              aria-label={`${value} out of 10`}
              title={mine === value ? "Clear score" : `${value}/10`}
              disabled={disabled}
              onClick={() => onChange(mine === value ? null : value)}
              className={`flex-1 h-8 rounded text-xs font-medium transition-colors disabled:opacity-60 ${
                filled
                  ? "bg-brand-600 text-white hover:bg-brand-500"
                  : dark
                    ? "bg-gray-800 text-gray-400 hover:bg-gray-700"
                    : "bg-gray-200 text-gray-600 hover:bg-gray-300"
              }`}
            >
              {value}
            </button>
          )
        })}
      </div>
    </div>
  )
}
