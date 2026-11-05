import { useAuth } from "../context/AuthContext"

// What the connected server supports, from GET /server/info "api_version". An older server is
// missing newer routes, so the app hides those features instead of showing errors.
// While the version isn't known (offline, still loading) everything is assumed to work.
export const APP_API_VERSION = 3

export function useServerFeatures() {
  const { serverInfo } = useAuth()
  const version = serverInfo ? (serverInfo.api_version ?? 1) : null
  const known = version !== null
  const v2 = !known || version >= 2
  return {
    // Version 1 servers lack the reader features the "older server" notice lists
    serverOutdated: known && version < 2,
    ratings: v2,
    chapterMarks: v2,
    seriesDetails: v2,
    // 3: the owner installs server updates from Settings
    serverUpdates: !known || version >= 3,
  }
}
