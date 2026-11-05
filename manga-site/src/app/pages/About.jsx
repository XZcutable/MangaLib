import { Link } from "react-router"
import { useAuth } from "../context/AuthContext"
import { useStyles } from "../hooks/useStyles"
import { serverBase } from "../lib/api"
import { canSelfUpdate, RELEASES_PAGE } from "../lib/updater"
import { APP_VERSION, GITHUB_PAGE } from "../lib/version"
import { APP_API_VERSION } from "../lib/features"
import { UpdatesSection } from "../components/settings/UpdatesSection"

const CREDITS = [
  { name: "Flask", url: "https://flask.palletsprojects.com/" },
  { name: "PyMuPDF", url: "https://pymupdf.readthedocs.io/" },
  { name: "React", url: "https://react.dev/" },
  { name: "Capacitor", url: "https://capacitorjs.com/" },
  { name: "shadcn/ui (MIT)", url: "https://ui.shadcn.com/" },
  { name: "Lucide icons", url: "https://lucide.dev/" },
  { name: "Photos from Unsplash", url: "https://unsplash.com/license" },
]

export function About() {
  const s = useStyles()
  const { siteName, server, serverInfo, user } = useAuth()
  const rows = [
    ["App", `v${APP_VERSION}`],
    ["Server", serverInfo?.version ? `v${serverInfo.version}` : "unknown"],
    ["API", `${serverInfo?.api_version ?? "?"} (app supports ${APP_API_VERSION})`],
    ["Address", server || `${window.location.origin}${serverBase()}`],
  ]
  const link = "text-brand-500 hover:text-brand-400"

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className={`mb-4 ${s.dark ? "text-white" : "text-gray-900"}`}>About {siteName}</h1>

      <section className={s.card}>
        <h2 className={s.heading}>myMangaLib</h2>
        <p className={`text-sm mb-4 ${s.muted}`}>
          A self-hosted manga server. You're using the app version below with the server at this address.
        </p>
        <dl className={`divide-y ${s.divider}`}>
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 py-2">
              <dt className={s.muted}>{label}</dt>
              <dd className={`${s.text} text-right break-all`}>{value}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-4 mt-4 text-sm">
          <a href={RELEASES_PAGE} target="_blank" rel="noopener noreferrer" className={link}>
            What's new (releases)
          </a>
          <a href={GITHUB_PAGE} target="_blank" rel="noopener noreferrer" className={link}>
            Project on GitHub
          </a>
          {user?.is_owner && (
            <Link to="/settings#server-updates" className={link}>
              Server updates
            </Link>
          )}
        </div>
      </section>

      {canSelfUpdate && <UpdatesSection />}

      <section className={s.card}>
        <h2 className={s.heading}>Built with</h2>
        <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
          {CREDITS.map((credit) => (
            <li key={credit.name}>
              <a href={credit.url} target="_blank" rel="noopener noreferrer" className={link}>
                {credit.name}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
