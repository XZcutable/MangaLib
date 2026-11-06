import { useEffect, useState } from "react"
import { useAppLock } from "../../context/AppLockContext"
import { useStyles } from "../../hooks/useStyles"
import { LOCK_DELAYS, lockAvailability } from "../../lib/appLock"
import { SettingSwitch } from "./SettingSwitch"

// Android app only (Settings shows it when canUseAppLock)
export function AppLockSection() {
  const s = useStyles()
  const { settings, setEnabled, setDelay, setHideInRecents } = useAppLock()
  const [availability, setAvailability] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    lockAvailability().then(setAvailability)
  }, [])

  // Can't be turned on without a screen lock; turning it off always works
  const cannotEnable = !settings.enabled && availability && !availability.available

  return (
    <section id="app-lock" className={`${s.card} scroll-mt-20`}>
      <h2 className={s.heading}>App lock</h2>
      <p className={`text-sm mb-4 ${s.muted}`}>Applies on this phone.</p>
      <div className={`divide-y ${s.divider}`}>
        <SettingSwitch
          label="Lock with face or fingerprint"
          description="Asks for your face, fingerprint or screen lock when the app opens or comes back."
          checked={settings.enabled}
          disabled={busy || !availability || cannotEnable}
          disabledReason={cannotEnable ? availability.message : undefined}
          onChange={async (on) => {
            setBusy(true)
            try {
              await setEnabled(on)
            } finally {
              setBusy(false)
            }
          }}
        />
        {settings.enabled && (
          <div className="py-3">
            <p className={s.text}>Lock after</p>
            <p className={`text-sm mt-0.5 mb-3 ${s.muted}`}>How long the app can be in the background before it locks.</p>
            <div className="flex flex-wrap gap-3" role="radiogroup" aria-label="Lock after">
              {LOCK_DELAYS.map((option) => {
                const selected = option.minutes === settings.delayMinutes
                return (
                  <button
                    key={option.minutes}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setDelay(option.minutes)}
                    className={`px-4 py-2 rounded-full border transition-colors ${
                      selected
                        ? "border-brand-500 bg-brand-600/15"
                        : s.dark
                          ? "border-gray-700 hover:bg-gray-800"
                          : "border-gray-300 hover:bg-gray-100"
                    }`}
                  >
                    <span className={s.text}>
                      {selected ? "✓ " : ""}
                      {option.label}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
        <SettingSwitch
          label="Hide in recent apps"
          description="Blanks the app's preview in the app switcher. Android also blocks screenshots while this is on."
          checked={settings.hideInRecents}
          onChange={setHideInRecents}
        />
      </div>
    </section>
  )
}
