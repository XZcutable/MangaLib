import { useState } from "react"
import { toast } from "sonner"
import { FileDown, Save, Share2, Upload } from "lucide-react"
import { useStyles } from "../../hooks/useStyles"
import { pickApk, restoreBackup, saveBackup, shareApp } from "../../lib/appShare"
import { InstallFromFileDialog } from "../InstallFromFileDialog"

// Android app only: send the app to a nearby phone, install one someone sent, and back up settings
export function ShareAppSection() {
  const s = useStyles()
  const [busy, setBusy] = useState(null)
  const [picked, setPicked] = useState(null)

  const run = async (name, action) => {
    setBusy(name)
    try {
      await action()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setBusy(null)
    }
  }

  const choose = () =>
    run("pick", async () => {
      const info = await pickApk()
      if (!info.cancelled) setPicked(info)
    })

  const backup = () =>
    run("backup", async () => {
      const result = await saveBackup()
      if (!result.cancelled) toast.success(`Backup saved${result.folder ? ` to ${result.folder}` : ""}`)
    })

  const restore = () =>
    run("restore", async () => {
      const result = await restoreBackup()
      if (result.cancelled) return
      toast.success("Backup restored")
      // Every part of the app reads its settings at start
      setTimeout(() => window.location.reload(), 800)
    })

  return (
    <section className={s.card}>
      <h2 className={s.heading}>Share the app</h2>
      <p className={`text-sm mb-3 ${s.muted}`}>
        Send this app to someone nearby with Quick Share, Bluetooth or any other app. No internet needed. They can
        install it by opening the file, or with Install from a file if they already have myMangaLib.
      </p>
      <div className="flex flex-wrap gap-2 mb-6">
        <button className={s.button} disabled={busy !== null} onClick={() => run("share", shareApp)}>
          <span className="inline-flex items-center gap-2"><Share2 className="w-4 h-4" /> Share this app</span>
        </button>
        <button className={s.button} disabled={busy !== null} onClick={choose}>
          <span className="inline-flex items-center gap-2">
            <FileDown className="w-4 h-4" /> {busy === "pick" ? "Reading…" : "Install from a file"}
          </span>
        </button>
      </div>

      <h3 className={s.subheading}>Backup</h3>
      <p className={`text-sm mb-3 ${s.muted}`}>
        Saves your settings, saved servers (not your logins) and a copy of this version to Download/myMangaLib.
        Restoring brings them back after reinstalling the app.
      </p>
      <div className="flex flex-wrap gap-2">
        <button className={s.button} disabled={busy !== null} onClick={backup}>
          <span className="inline-flex items-center gap-2"><Save className="w-4 h-4" /> {busy === "backup" ? "Saving…" : "Save a backup"}</span>
        </button>
        <button className={s.button} disabled={busy !== null} onClick={restore}>
          <span className="inline-flex items-center gap-2"><Upload className="w-4 h-4" /> Restore a backup</span>
        </button>
      </div>

      {picked && <InstallFromFileDialog info={picked} onClose={() => setPicked(null)} />}
    </section>
  )
}
