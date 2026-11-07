import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { Copy, Share2 } from "lucide-react"
import { useAuth } from "../context/AuthContext"
import { useStyles } from "../hooks/useStyles"
import { api, parseServerDate } from "../lib/api"
import { useServerFeatures } from "../lib/features"
import { addressReach, joinLink, shareBase } from "../lib/share"
import { QrCode } from "../components/QrCode"

const EXPIRY_CHOICES = [
  { days: 1, label: "1 day" },
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
]
const USE_CHOICES = [
  { value: "1", label: "1 person" },
  { value: "5", label: "5 people" },
  { value: "25", label: "25 people" },
  { value: "any", label: "Any number" },
]
const STATUS_LABELS = {
  active: "Active",
  invite_expired: "Expired",
  invite_used_up: "Used up",
  registration_closed: "Paused: sign-ups are closed",
}

const formatDate = (value) => parseServerDate(value).toLocaleDateString()

// Share the server as a QR code or link. People who can invite also make invite links here.
export function Share() {
  const { user, server, serverInfo, siteName } = useAuth()
  const features = useServerFeatures()
  const s = useStyles()

  const base = shareBase(serverInfo, server)
  const reach = addressReach(base)
  const canInvite = features.invites && Boolean(user?.can_invite)

  const [days, setDays] = useState(7)
  const [uses, setUses] = useState("1")
  const [created, setCreated] = useState(null) // { code, invite } of the invite just made
  const [invites, setInvites] = useState(null)

  const loadInvites = useCallback(() => {
    if (!features.invites) return
    api
      .invites()
      .then((data) => setInvites(data.invites))
      .catch(() => setInvites(null))
  }, [features.invites])
  useEffect(loadInvites, [loadInvites])

  // Older servers have no /join page, so their link is the plain address
  const link = created ? joinLink(base, created.code) : features.invites ? joinLink(base) : base

  const createInvite = async (event) => {
    event.preventDefault()
    try {
      const result = await api.createInvite({ expires_days: days, max_uses: uses === "any" ? null : Number(uses) })
      setCreated(result)
      loadInvites()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const cancelInvite = async (invite) => {
    if (!confirm("Cancel this invite? Its link stops working.")) return
    try {
      await api.deleteInvite(invite.id)
      if (created?.invite.id === invite.id) setCreated(null)
      loadInvites()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      toast.success("Link copied")
    } catch {
      toast.error("Couldn't copy. Press and hold the link to copy it instead.")
    }
  }
  // The Android WebView has no share sheet for links, but browsers on phones do
  const canShareLink = typeof navigator.share === "function"
  const shareLink = () =>
    navigator.share({ title: siteName, text: created ? `Join me on ${siteName}` : siteName, url: link }).catch(() => {})

  const usesText = (invite) => (invite.max_uses === null ? `${invite.uses} used` : `${invite.uses} of ${invite.max_uses} used`)

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className={`mb-4 ${s.dark ? "text-white" : "text-gray-900"}`}>Share {siteName}</h1>

      <section className={s.card}>
        <div className="flex flex-col items-center text-center gap-4">
          <QrCode value={link} label={created ? "Invite QR code" : "Server QR code"} />
          <div>
            <h2 className={`${s.heading} mb-1`}>{created ? "Invite link" : "Server link"}</h2>
            <p className={`text-sm ${s.muted}`}>
              {created
                ? `Anyone with this link can create an account${
                    created.invite.approved_on_join ? "." : ", which then waits for an admin's approval."
                  } It works for ${
                    created.invite.max_uses === null ? "any number of people" : created.invite.max_uses === 1 ? "one person" : `${created.invite.max_uses} people`
                  } until ${formatDate(created.invite.expires)}.`
                : serverInfo?.registration_open
                  ? "Scan with a phone camera or the app to log in or sign up."
                  : "Scan with a phone camera or the app to log in. New people need an invite."}
            </p>
          </div>
          <p className={`text-sm break-all ${s.text}`}>{link}</p>
          <div className="flex flex-wrap justify-center gap-2">
            <button className={s.button} onClick={copy}>
              <span className="inline-flex items-center gap-2"><Copy className="w-4 h-4" /> Copy link</span>
            </button>
            {canShareLink && (
              <button className={s.button} onClick={shareLink}>
                <span className="inline-flex items-center gap-2"><Share2 className="w-4 h-4" /> Share</span>
              </button>
            )}
            {created && (
              <button className={s.button} onClick={() => setCreated(null)}>Show the server link</button>
            )}
          </div>
          {reach !== "public" && (
            <p className="text-sm text-amber-500">
              {reach === "device"
                ? "This address only works on this device, so the link won't work for anyone else."
                : "This address only works on the same Wi‑Fi or private network."}
              {user?.is_owner
                ? " Set the address people use from outside in Settings → Users → Public address."
                : " Ask the server's owner to set a public address."}
            </p>
          )}
        </div>
      </section>

      {features.invites && (
        <section className={s.card}>
          <h2 className={s.heading}>Invite someone new</h2>
          {canInvite ? (
            <form onSubmit={createInvite} className="space-y-4">
              <div className="flex flex-wrap gap-4">
                <label className={`text-sm ${s.text}`}>
                  <span className="block mb-1">Works for</span>
                  <select className={s.input} value={uses} onChange={(event) => setUses(event.target.value)}>
                    {USE_CHOICES.map((choice) => (
                      <option key={choice.value} value={choice.value}>{choice.label}</option>
                    ))}
                  </select>
                </label>
                <label className={`text-sm ${s.text}`}>
                  <span className="block mb-1">Expires after</span>
                  <select className={s.input} value={days} onChange={(event) => setDays(Number(event.target.value))}>
                    {EXPIRY_CHOICES.map((choice) => (
                      <option key={choice.days} value={choice.days}>{choice.label}</option>
                    ))}
                  </select>
                </label>
              </div>
              <button className={s.primaryButton}>Create invite</button>
              <p className={`text-xs ${s.muted}`}>
                {user?.is_admin
                  ? "Your invites work even while sign-ups are closed, and their accounts are approved straight away."
                  : "Your invites work while sign-ups are open."}{" "}
                The link is only shown once, right after you create it.
              </p>
            </form>
          ) : (
            <p className={`text-sm ${s.muted}`}>Sign-ups are closed on this server, so only admins can invite people.</p>
          )}
        </section>
      )}

      {invites?.length > 0 && (
        <section className={s.card}>
          <h2 className={s.heading}>{user?.is_admin ? "Invites" : "Your invites"}</h2>
          <ul className={`border rounded-md divide-y ${s.divider}`}>
            {invites.map((invite) => (
              <li key={invite.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
                <div className="flex-1 min-w-[10rem]">
                  <p className={s.text}>
                    {STATUS_LABELS[invite.status] ?? invite.status}
                    {user?.is_admin && invite.created_by.username && (
                      <span className={`text-sm ${s.muted}`}> · by {invite.created_by.username}</span>
                    )}
                  </p>
                  <p className={`text-xs ${s.muted}`}>
                    {usesText(invite)} · expires {formatDate(invite.expires)}
                  </p>
                </div>
                <button className={`${s.dangerButton} py-1`} onClick={() => cancelInvite(invite)}>
                  {invite.status === "active" ? "Cancel" : "Remove"}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
