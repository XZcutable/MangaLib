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
    APP_ROOT_PATH = None
    APP_INSTANCE_PATH = None

    CONFIG_NAME = "config.toml"
    DEFAULT_DATABASE = "database.db"
    PLACEHOLDER_SECRET_KEY = "REPLACE ME"

    DEFAULT_CONFIG = """\
SECRET_KEY='REPLACE ME'
BEHIND_PROXY=false

ALLOW_NEW_USERS=false
AUTO_APPROVE_NEW_USERS=false
HIDE_MANGA=false
HIDE_TITLES=false

FETCH_BATCH_SIZE=30

# Folder of the built new front end (manga-site/dist). When set, it's served at / and the
# classic UI moves to /classic. Leave empty to keep the classic UI at /.
FRONTEND_PATH=''

# Web pages allowed to call /api/v1 from a browser. capacitor://localhost is the iOS app, http://localhost the Android app.
CORS_ORIGINS=['capacitor://localhost', 'http://localhost', 'https://localhost']
"""
from sqlalchemy import asc, desc
class SQL:
    ASC = asc
    DESC = desc
    ORDER = {
        "asc":asc,
        "desc":desc
    }