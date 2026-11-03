import { ListPage } from "../components/ListPage"

// Series by release year. The year comes from file names like "v01 (2019)".
export function Newest() {
  return (
    <ListPage
      title="New Releases"
      description="Series that came out most recently. Release years are read from file names; series without one are listed last."
      list="newest"
    />
  )
}
