class ROUTE:
    LATEST = "/latest"
    ALL = "/all"
    HISTORY = "/history"
    FAVORITES = "/favorites"
    RANDOM = "/random"
    RANDOM_UNREAD = "/random-unread"

    REGISTER = "/register"
    CHANGE_USERNAME = "/auth/change-username"
    CHANGE_PASSWORD = "/auth/change-password"
    LOGIN = "/login"

class ENDPOINT:
    MANGA_RESUME = "manga.resume"
    MANGA_READ = "manga.read"
    MANGA_INFO = "manga.info"
    HOME = "home"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REGISTER = "auth.register"

class HTML:
    HOME = "manga/home.html"
    INFINITE_SCROLL = "manga/manga_infinite_scroll.html"
    HISTORY = "manga/history.html"
    FAVORITES = "manga/favorites.html"
    INFO = "manga/info.html"
    PAGE = "manga/page.html"

class VAR:
    HIDE_MANGA = "HIDE_MANGA"
    HIDE_TITLES = "HIDE_TITLES"

    ASC = "asc"
    DESC = "desc"