import { ListPage } from "../components/ListPage"

// Series with at least one score, highest average first
export function TopRated() {
  return (
    <ListPage
      title="Top Rated"
      description="Series scored by readers on this server, highest average first."
      list="rated"
    />
  )
}
