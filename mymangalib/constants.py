class ROUTE:
    LATEST = "/latest"
    ALL = "/all"
    HISTORY = "/history"
    FAVORITES = "/favorites"
    QUEUED = "/queued"
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
    HOME = "manga.home"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REGISTER = "auth.register"

class HTML:
    HOME = "manga/home.html"
    INFINITE_SCROLL = "manga/manga_infinite_scroll.html"
    HISTORY = "manga/history.html"
    FAVORITES = "manga/favorites.html"
    QUEUED = "manga/queued.html"
    INFO = "manga/info.html"
    PAGE = "manga/page.html"

class VAR:
    HIDE_MANGA = "HIDE_MANGA"
    HIDE_TITLES = "HIDE_TITLES"

    ASC = "asc"
    DESC = "desc"

class ENV:
    CONFIG_NAME = "config.toml"
    DEFAULT_CONFIG = """\
SECRET_KEY="REPLACE ME"
SERVER_NAME="0.0.0.0:6883"
ALLOW_NEW_USERS=false
AUTO_APPROVE_NEW_USERS=false

DATABASE_PATH='.'

HIDE_MANGA=false
HIDE_TITLES=false

FETCH_BATCH_SIZE=30
"""
    DEFAULT_DATABASE_NAME = "database.db"
    # This would be the instance folder
    DEFAULT_DATABASE_PATH = "."

from sqlalchemy import asc, desc
class SQL:
    ASC = asc
    DESC = desc
    ORDER = {
        "asc":asc,
        "desc":desc
    }