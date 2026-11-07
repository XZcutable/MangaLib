class ROUTE:
    LATEST = "/latest"
    ALL = "/all"
    HISTORY = "/history"
    FAVORITES = "/favorites"
    QUEUED = "/queued"
    RANDOM = "/random"
    RANDOM_UNREAD = "/random-unread"

    REGISTER = "/register"
    JOIN = "/join"
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
    AUTH_JOIN = "auth.join"

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

# The name in the browser tab and the interface. The owner can also change it in Settings.
SITE_NAME='myMangaLib'

# The address people use to reach this server from outside, e.g. 'https://manga.example.com'. Invite links
# and QR codes use it. Empty: the app shares the address it's connected to. The owner can change it in Settings.
PUBLIC_URL=''

# Library folders for a new server, e.g. ['/var/manga']. On a start with no library folders yet,
# they're added and scanned. After that, manage folders in Settings > Library.
LIBRARY_PATHS=[]

# A library folder that moved (or is now mounted somewhere else), e.g. {'/mnt/media/manga' = '/var/manga'}.
# Done once at startup: the manga keep their reading progress. Settings > Library can do the same.
LIBRARY_MOVES={}

# Folder of the built new front end (manga-site/dist). When set, it's served at / and the
# classic UI moves to /classic. Leave empty to keep the classic UI at /.
FRONTEND_PATH=''

# For a reverse proxy that serves this at a sub-path and passes the path through unchanged, e.g. '/manga'
# for https://example.com/manga/. A proxy that removes the prefix should send X-Forwarded-Prefix instead
# (with BEHIND_PROXY=true). Leave empty when the server has its own address.
URL_PREFIX=''

# Web pages allowed to call /api/v1 from a browser. capacitor://localhost is the iOS app, http://localhost the Android app.
CORS_ORIGINS=['capacitor://localhost', 'http://localhost', 'https://localhost']

# Server updates. The server checks GitHub every UPDATE_CHECK_HOURS and downloads new versions in the
# background; nothing is installed until the owner applies it in Settings. AUTO_UPDATE=false (or
# `mymangalib serve --no-auto-update`) turns automatic checks off; the owner can still check by hand.
AUTO_UPDATE=true
UPDATE_CHECK_HOURS=6
UPDATE_REPO='XZcutable/MangaLib'
"""
from sqlalchemy import asc, desc
class SQL:
    ASC = asc
    DESC = desc
    ORDER = {
        "asc":asc,
        "desc":desc
    }