// Tells the "server is updating" overlay when the server is restarting. The API client reports the
// supervisor's 503 answers (server_updating / server_starting); Settings reports the owner's own "Apply".
const listeners = new Set()

export function subscribeRestarting(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// reason: "updating" | "starting"
export function reportRestarting(reason = "updating") {
  for (const listener of listeners) listener(reason)
}

export const RESTART_CODES = { server_updating: "updating", server_starting: "starting" }
