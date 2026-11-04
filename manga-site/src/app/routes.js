import { createBrowserRouter } from "react-router"
import { Layout } from "./components/Layout"
import { RequireAuth } from "./components/RequireAuth"
import { Home } from "./pages/Home"
import { Latest } from "./pages/Latest"
import { All } from "./pages/All"
import { Newest } from "./pages/Newest"
import { Random } from "./pages/Random"
import { Unread } from "./pages/Unread"
import { Settings } from "./pages/Settings"
import { History } from "./pages/History"
import { Favorites } from "./pages/Favorites"
import { Bookmarks } from "./pages/Bookmarks"
import { Search } from "./pages/Search"
import { TopRated } from "./pages/TopRated"
import { Downloads } from "./pages/Downloads"
import { MangaInfo } from "./pages/MangaInfo"
import { Reader } from "./pages/Reader"
import { Connect } from "./pages/Connect"
import { Logout } from "./pages/Logout"
import { NotFound } from "./pages/NotFound"
import { BASE_PATH } from "./lib/base"
export const router = createBrowserRouter([
  { path: "/connect", Component: Connect },
  {
    Component: RequireAuth,
    children: [
      // The reader is full screen, without the navbar and footer
      { path: "/read/:mangaId/:chapter/:page", Component: Reader },
      {
        path: "/",
        Component: Layout,
        children: [
          { index: true, Component: Home },
          { path: "latest", Component: Latest },
          { path: "all", Component: All },
          { path: "newest", Component: Newest },
          { path: "random", Component: Random },
          { path: "unread", Component: Unread },
          { path: "top-rated", Component: TopRated },
          { path: "downloads", Component: Downloads },
          { path: "search", Component: Search },
          { path: "manga/:mangaId", Component: MangaInfo },
          { path: "settings", Component: Settings },
          { path: "history", Component: History },
          { path: "favorites", Component: Favorites },
          { path: "bookmarks", Component: Bookmarks },
          { path: "logout", Component: Logout },
          { path: "*", Component: NotFound },
        ],
      },
    ],
  },
],
  // Under a sub-path (e.g. /manga) every route lives below it
  { basename: BASE_PATH || "/" },
)
