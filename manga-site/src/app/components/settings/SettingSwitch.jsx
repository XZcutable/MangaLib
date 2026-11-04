import { useId } from "react"
import { useStyles } from "../../hooks/useStyles"

// An on/off setting. The label and description never change with the state, so the layout stays put;
// only the switch moves. When disabled it's dimmed and says why.
export function SettingSwitch({ label, description, checked, onChange, disabled = false, disabledReason }) {
  const s = useStyles()
  const id = useId()

  return (
    <div className={`flex items-start justify-between gap-4 py-3 ${disabled ? "opacity-50" : ""}`}>
      <div className="flex-1 min-w-0">
        <label htmlFor={id} className={`block ${s.text} ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}>
          {label}
        </label>
        <p className={`text-sm mt-0.5 ${s.muted}`}>
          {disabled && disabledReason ? disabledReason : description}
        </p>
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative shrink-0 mt-0.5 w-11 h-6 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 disabled:cursor-not-allowed ${
          checked ? "bg-brand-600" : s.dark ? "bg-gray-700" : "bg-gray-300"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  )
}
