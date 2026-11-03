import { Navigate } from "react-router"
// The server has no release dates, so "newest" and "latest" are the same list
export function Newest() {
  return <Navigate to="/latest" replace />
}
