import { ListPage } from "../components/ListPage"

// Series that most recently got new volumes or chapters, including newly added series
export function Latest() {
  return (
    <ListPage
      title="Recently Updated"
      description="Series with new volumes or chapters, most recent first."
      list="updated"
      showUpdated
    />
  )
}
