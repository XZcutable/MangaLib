// The app's recent warnings, errors and failed requests, kept in memory so a bug report can include
// them. Nothing is sent unless the user leaves "Include app logs" on, and they can read it first.

const MAX_ENTRIES = 200
const MAX_TEXT = 2000
const entries = []
let installed = false

// Tokens in headers, image URLs (?t=) and invite codes would let someone use the account
const SECRETS = /(Bearer\s+|[?&](?:t|token|code)=|"token"\s*:\s*")[^\s&"']+/gi

export function redact(text) {
  return String(text).replace(SECRETS, "$1[hidden]")
}

function describe(value) {
  if (value instanceof Error) return value.stack || `${value.name}: ${value.message}`
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function addLog(level, ...parts) {
  const text = redact(parts.map(describe).join(" ")).slice(0, MAX_TEXT)
  entries.push({ time: new Date().toISOString(), level, text })
  if (entries.length > MAX_ENTRIES) entries.splice(0, entries.length - MAX_ENTRIES)
}

// The log as text, oldest first, for a bug report
export function logText() {
  return entries.map((entry) => `${entry.time} ${entry.level.toUpperCase()} ${entry.text}`).join("\n")
}

export function installLogBuffer() {
  if (installed) return
  installed = true
  for (const level of ["warn", "error"]) {
    const original = console[level].bind(console)
    console[level] = (...args) => {
      addLog(level, ...args)
      original(...args)
    }
  }
  window.addEventListener("error", (event) => {
    addLog("error", event.error ?? event.message, event.filename ? `at ${event.filename}:${event.lineno}` : "")
  })
  window.addEventListener("unhandledrejection", (event) => addLog("error", "Unhandled promise rejection:", event.reason))
  addLog("info", `App started at ${location.pathname}`)
}
