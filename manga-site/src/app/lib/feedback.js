// Labels and helpers for feedback (server/feedback.py). The server decides who sees what and which
// status changes are allowed; the app only shows them.
import { Capacitor } from "@capacitor/core"
import { APP_VERSION } from "./version"
import { APP_API_VERSION } from "./features"

export const KINDS = [
  { id: "bug", label: "Bug", hint: "Something doesn't work the way it should." },
  { id: "app_idea", label: "App idea", hint: "Something the app could do, on the web or on your phone." },
  { id: "server_idea", label: "Server idea", hint: "Something the server could do: library, accounts, sharing…" },
  { id: "content_request", label: "Request a series", hint: "A manga you'd like added to the library." },
  { id: "content_problem", label: "Problem with a series", hint: "Missing or broken pages, wrong order, wrong files." },
  { id: "details", label: "Wrong series details", hint: "Title, summary, genres or year are wrong." },
]
export const KIND_LABELS = Object.fromEntries(KINDS.map((kind) => [kind.id, kind.label]))

export const STATUS_LABELS = {
  new: "New",
  triaging: "Being reviewed",
  needs_info: "Needs more info",
  planning: "Being planned",
  plan_ready: "Plan ready",
  changes_requested: "Plan changes asked",
  approved: "Approved",
  in_progress: "In progress",
  done: "Done",
  declined: "Declined",
  duplicate: "Duplicate",
}

// What the staff buttons say for each status they can move an item to
export const STATUS_ACTIONS = {
  new: "Reopen",
  needs_info: "Ask for more info",
  approved: "Approve",
  changes_requested: "Request changes",
  in_progress: "Start",
  done: "Mark done",
  declined: "Decline",
  duplicate: "Duplicate",
}

export function statusTone(status) {
  if (status === "done") return "green"
  if (status === "declined" || status === "duplicate") return "gray"
  if (status === "needs_info" || status === "plan_ready") return "amber"
  return "brand"
}

// Sent with every report so the owner knows where it happened. Shown to the user before sending.
export function feedbackContext(fromPath) {
  return {
    app_version: APP_VERSION,
    app_api_version: APP_API_VERSION,
    platform: Capacitor.getPlatform(),
    user_agent: navigator.userAgent,
    screen: `${window.innerWidth}x${window.innerHeight} @${window.devicePixelRatio || 1}x`,
    language: navigator.language,
    page: fromPath || null,
  }
}

export const MAX_SCREENSHOTS = 3
export const MAX_SCREENSHOT_MB = 5
