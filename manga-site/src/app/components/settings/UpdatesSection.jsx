import { useState } from "react"
import { RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { useUpdates } from "../../context/UpdateContext"
import { useStyles } from "../../hooks/useStyles"
import { autoCheckEnabled, RELEASES_PAGE, setAutoCheck } from "../../lib/updater"
import { SettingSwitch } from "./SettingSwitch"

// Android app only: the installed version, automatic checks and a manual check
export function UpdatesSection() {
  const s = useStyles()
  const { version, update, status, check, openDialog } = useUpdates()
  const [autoCheck, setAutoCheckState] = useState(autoCheckEnabled)

  const checkNow = async () => {
    try {
      const found = await check({ manual: true })
      if (!found) toast.success(`You have the latest version (${version})`)
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <section className={s.card}>
      <h2 className={s.heading}>App updates</h2>
      <p className={`text-sm mb-2 ${s.muted}`}>
        Installed version: <span className={s.text}>{version ?? "…"}</span>
        {update && (
          <>
            {" • "}
            <button className="text-brand-500 hover:text-brand-400" onClick={openDialog}>
              Version {update.version} is available
            </button>
          </>
        )}
      </p>
      <div className={`divide-y ${s.divider}`}>
        <SettingSwitch
          label="Check for updates automatically"
          description="When the app opens, at most every 6 hours. New versions come from GitHub Releases."
          checked={autoCheck}
          onChange={(value) => {
            setAutoCheck(value)
            setAutoCheckState(value)
          }}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3 mt-3">
        <button className={s.button} onClick={checkNow} disabled={status === "checking" || status === "downloading"}>
          <span className="inline-flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${status === "checking" ? "animate-spin" : ""}`} />
            {status === "checking" ? "Checking…" : "Check for updates"}
          </span>
        </button>
        <a href={RELEASES_PAGE} target="_blank" rel="noopener noreferrer" className="text-sm text-brand-500 hover:text-brand-400">
          All releases
        </a>
      </div>
    </section>
  )
}
