import { useState } from "react"
import { AlertTriangle, PackageCheck, ShieldCheck } from "lucide-react"
import { useStyles } from "../hooks/useStyles"
import { classify, saveBackup, source, uninstallApp } from "../lib/appShare"
import { canInstall, installUpdate, openInstallSettings } from "../lib/updater"

// Shown after picking an APK in Settings → Share the app. Official updates install like normal updates.
// Anything else gets a warning first; builds that can't install over this one (another key, or older)
// go through a backup and an uninstall.
export function InstallFromFileDialog({ info, onClose }) {
  const s = useStyles()
  const kind = classify(info)
  const from = source(info)
  const needsTrust = from !== "official" && (kind === "update" || kind === "replace")

  const [trusted, setTrusted] = useState(false)
  const [confirmed, setConfirmed] = useState(!needsTrust)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [needsPermission, setNeedsPermission] = useState(false)
  const [saved, setSaved] = useState(null) // the backup's file names and folder
  const [skippedBackup, setSkippedBackup] = useState(false)

  const run = async (action) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  const install = () =>
    run(async () => {
      if (!(await canInstall())) {
        setNeedsPermission(true)
        await openInstallSettings()
        return
      }
      setNeedsPermission(false)
      await installUpdate(info.path)
    })

  const backup = () =>
    run(async () => {
      const result = await saveBackup({ newApk: info })
      if (!result.cancelled) setSaved(result)
    })

  const version = info.versionName
  const installed = info.installedVersionName
  const why =
    info.signatureKnown && !info.sameSigner
      ? from === "official"
        ? "This is the official version, and the app on this phone was signed by someone else."
        : "It's signed differently from the app on this phone."
      : `It's an older version than the one on this phone (${installed}).`

  let body
  if (kind === "invalid" || kind === "other-app") {
    body = (
      <p className={`text-sm ${s.muted}`}>
        {kind === "invalid" ? "This file isn't an Android app." : `This is a different app (${info.packageName}), not myMangaLib.`}
      </p>
    )
  } else if (kind === "same") {
    body = <p className={`text-sm ${s.muted}`}>This phone already has version {version}.</p>
  } else if (!confirmed) {
    body = (
      <div className="space-y-4">
        <div className="flex gap-3 p-3 rounded-md border border-amber-500/60 bg-amber-500/10">
          <AlertTriangle className="w-5 h-5 shrink-0 text-amber-500" />
          <div className={`text-sm space-y-2 ${s.text}`}>
            <p className="font-semibold">
              {from === "unknown" ? "Android couldn't check who made this file." : "This isn't an official myMangaLib build."}
            </p>
            <p>
              It may have been made or changed by someone other than the myMangaLib developers. An app can do anything this one can,
              including seeing your servers, your logins and what you read. Only install it if you trust the person
              who gave it to you.
            </p>
          </div>
        </div>
        <label className={`flex items-start gap-2 text-sm ${s.text}`}>
          <input type="checkbox" className="mt-1" checked={trusted} onChange={(event) => setTrusted(event.target.checked)} />
          I trust where this file came from
        </label>
        <button className={s.primaryButton} disabled={!trusted} onClick={() => setConfirmed(true)}>
          Continue
        </button>
      </div>
    )
  } else if (kind === "update") {
    body = (
      <div className="space-y-4">
        <p className={`text-sm ${s.muted}`}>
          Version {version} installs over this one ({installed}). Your servers, logins and downloads stay.
        </p>
        {needsPermission && (
          <p className={`text-sm p-3 rounded-md ${s.dark ? "bg-brand-950/50 text-brand-200" : "bg-brand-50 text-brand-900"}`}>
            Turn on <strong>Allow from this source</strong> for myMangaLib, then come back and tap Install again.
          </p>
        )}
        <button className={s.primaryButton} disabled={busy} onClick={install}>
          {busy ? "Opening installer…" : "Install"}
        </button>
      </div>
    )
  } else if (!saved && !skippedBackup) {
    body = (
      <div className="space-y-4">
        <p className={`text-sm ${s.text}`}>
          Android can't install version {version} over this one. {why} The app on this phone has to be uninstalled
          first, which deletes everything it keeps here, including downloaded chapters.
        </p>
        <p className={`text-sm ${s.muted}`}>
          Save a backup first, to the Download folder. It holds your settings and saved servers (not your logins), a
          copy of this version ({installed}) so you can go back, and the new version.
        </p>
        <button className={s.primaryButton} disabled={busy} onClick={backup}>
          {busy ? "Saving…" : "Save a backup"}
        </button>
        <button className="block text-sm text-brand-500" disabled={busy} onClick={() => setSkippedBackup(true)}>
          Continue without a backup
        </button>
      </div>
    )
  } else {
    const newFile = saved?.newApk ?? info.fileName ?? "the new app file"
    const place = saved?.folder ? saved.folder : "your files"
    body = (
      <div className="space-y-4">
        {saved && (
          <p className={`text-sm flex items-center gap-2 ${s.text}`}>
            <PackageCheck className="w-4 h-4 text-green-500" /> Backup saved{saved.folder ? ` to ${saved.folder}` : ""}.
          </p>
        )}
        <ol className={`text-sm list-decimal pl-5 space-y-2 ${s.text}`}>
          <li>Uninstall this app with the button below.</li>
          <li>In your Files app, open {place} and tap <strong>{newFile}</strong> to install it.</li>
          <li>
            Open myMangaLib, tap <strong>Restore a backup</strong> on the first screen and pick{" "}
            {saved ? <strong>{saved.backup}</strong> : "your backup"}. Then log in again.
          </li>
        </ol>
        {saved && (
          <p className={`text-xs ${s.muted}`}>
            To go back later: uninstall, install {saved.currentApk} from the same folder, and restore the backup again.
          </p>
        )}
        <button className={s.dangerButton} disabled={busy} onClick={() => run(uninstallApp)}>
          Uninstall myMangaLib
        </button>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[70] bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="install-file-title"
        className={`w-full sm:max-w-md max-h-[90vh] overflow-y-auto rounded-t-lg sm:rounded-lg border p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] ${
          s.dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
        }`}
      >
        <h2 id="install-file-title" className={`flex items-center gap-2 mb-1 ${s.dark ? "text-white" : "text-gray-900"}`}>
          {from === "official" ? <ShieldCheck className="w-5 h-5 text-green-500" /> : <AlertTriangle className="w-5 h-5 text-amber-500" />}
          {kind === "invalid" || kind === "other-app" ? "Can't install this file" : `myMangaLib ${version}`}
        </h2>
        {info.valid && info.samePackage && (
          <p className={`text-xs mb-4 ${s.muted}`}>
            {from === "official" ? "Official build" : from === "custom" ? "Custom build" : "Unverified build"}
            {" · "}you have {installed}
            {info.fileName ? ` · ${info.fileName}` : ""}
          </p>
        )}
        {body}
        {error && <p className="text-sm text-red-500 mt-3">{error}</p>}
        <div className="mt-5 flex justify-end">
          <button className={s.button} disabled={busy} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
