import { useAuth } from "../context/AuthContext"

// What the connected server supports, from GET /server/info "api_version". An older server is
// missing newer routes, so the app hides those features instead of showing errors.
// While the version isn't known (offline, still loading) everything is assumed to work.
export const APP_API_VERSION = 2

export function useServerFeatures() {
  const { serverInfo } = useAuth()
  const version = serverInfo ? (serverInfo.api_version ?? 1) : null
  const known = version !== null
  const v2 = !known || version >= 2
  return {
    serverOutdated: known && version < APP_API_VERSION,
    ratings: v2,
    chapterMarks: v2,
    seriesDetails: v2,
  }
}
