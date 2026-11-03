"""JSON API for external clients (the mobile app and the new web front end).

Every route takes and returns JSON, authenticates with `Authorization: Bearer <token>`
(from POST /auth/login), and reports errors as {"error": {"code", "message"}}.
Image routes also accept the token as ?t= because <img> tags can't send headers.
"""
import os
from importlib import metadata

from flask import Flask, Blueprint, request, g, current_app, url_for, abort, send_file
from werkzeug.exceptions import HTTPException
from sqlalchemy import select, func
from flask_cors import CORS

from ..auth import API_V1_PREFIX, api_access, api_error, check_credentials, register_account, registration_rules, get_owner
from ..database import db
from ..enum import Access
from ..models import Manga, ContentTag, User
from ..server import library, tokens, thumbnails
from . import manga as manga_views

bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

API_VERSION = 1
IMAGE_MAX_AGE = 10*24*60*60
MAX_BATCH_SIZE = 100
DEFAULT_CORS_ORIGINS = [
    "capacitor://localhost",   # iOS app
    "http://localhost",        # Android app (http so it can load images from plain-http servers)
    "https://localhost",
]

def init_app(app: Flask):
    origins = app.config.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    if isinstance(origins, str):
        # Allows FLASK_CORS_ORIGINS="https://a.example,https://b.example"
        origins = [origin.strip() for origin in origins.split(",") if origin.strip()]
    CORS(app, resources={f"{API_V1_PREFIX}*": {"origins": origins}},
         allow_headers=["Authorization", "Content-Type"], methods=["GET", "POST", "PUT", "DELETE"])

    @app.errorhandler(HTTPException)
    def json_errors_for_api(error: HTTPException):
        if request.path.startswith(API_V1_PREFIX):
            return api_error(error.code, error.name.lower().replace(" ", "_"), error.description)
        return error

def thumbnail_cache_dir() -> str:
    return current_app.config.get("THUMBNAIL_CACHE_PATH") or os.path.join(current_app.instance_path, "cache", "covers")

def batch_size() -> int:
    return current_app.config.get("FETCH_BATCH_SIZE", 30)

def int_arg(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(request.args.get(name, default))
    except ValueError:
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value

def json_body() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}

def optional_bool(body: dict, key: str) -> bool | None:
    value = body.get(key)
    return value if isinstance(value, bool) else None

def get_manga_or_404(manga_id: int) -> Manga:
    manga = db.Manga.fromID(manga_id)
    if manga is None:
        abort(404, description=f"Manga {manga_id} not found")
    return manga

def cover_url(manga_id: int) -> str:
    return url_for("api_v1.cover", manga_id=manga_id)

def page_image_url(manga_id: int, chapter_number: int, page_number: int) -> str:
    return url_for("api_v1.page_image", manga_id=manga_id, chapter_number=chapter_number, page_number=page_number)

def paged_response(query, offset: int, limit: int) -> dict:
    """One batch of a (id, title) query, with cover URLs and the user's reading state."""
    rows = library.fetch(query, offset, limit)
    states = library.reading_state(g.user.id, [row["id"] for row in rows])
    items = []
    for row in rows:
        state = states.get(row["id"], {})
        items.append({
            "id": row["id"],
            "title": row["title"],
            "cover_url": cover_url(row["id"]),
            "total_chapters": state.get("total_chapters", 0),
            "release_year": state.get("release_year"),
            "last_updated": state.get("last_updated"),
            "progress": state.get("progress", 0.0),
            "user": state.get("user"),
        })
    total = library.count(query)
    next_offset = offset + len(items)
    return {
        "items": items,
        "offset": offset,
        "total": total,
        "next_offset": next_offset if next_offset < total else None,
    }

def account_json(user: User) -> dict:
    """The logged-in user. Admins also get how many sign-ups are waiting, for the badge in the app."""
    data = user.toJson()
    if data["is_admin"]:
        data["pending_users"] = db.session.scalar(select(func.count()).select_from(User).where(~User.approved))
    return data

# --- Server ---

@bp.route("/server/info")
def server_info():
    try:
        version = metadata.version("mymangalib")
    except metadata.PackageNotFoundError:
        version = None
    needs_setup = get_owner() is None
    return {
        "name": "myMangaLib",
        "version": version,
        "api_version": API_VERSION,
        "needs_setup": needs_setup,
        "registration_open": needs_setup or bool(current_app.config.get("ALLOW_NEW_USERS")),
        "hide_titles": manga_views.HIDE_TITLES,
        # Where the classic web interface is: /classic/ when this server also serves the new one
        "classic_ui_path": current_app.config.get("CLASSIC_UI_PATH", "/"),
    }

# --- Auth ---

@bp.route("/auth/login", methods=["POST"])
def login():
    body = json_body()
    username, password = body.get("username"), body.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        return api_error(400, "bad_request", "username and password are required")

    user, error = check_credentials(username, password)
    if error is not None:
        # One message for both bad username and bad password so usernames can't be probed
        if error == 'Account is waiting for approval':
            return api_error(403, "not_approved", error)
        return api_error(401, "invalid_credentials", "Incorrect username or password")

    token = tokens.create_token(user, str(body.get("device") or request.user_agent.string or ""))
    return {"token": token, "user": account_json(user)}

@bp.route("/auth/register", methods=["POST"])
def register():
    body = json_body()
    username, password = body.get("username"), body.get("password")
    if not isinstance(username, str) or not username.strip():
        return api_error(400, "bad_request", "Username is required")
    if not isinstance(password, str) or not password:
        return api_error(400, "bad_request", "Password is required")

    registration_open, auto_approve = registration_rules()
    user, error = register_account(username.strip(), password, registration_open, auto_approve)
    if error is not None:
        status, code = (403, "registration_closed") if error == 'Registration is closed' else (409, "username_taken")
        return api_error(status, code, error)
    return {"user": user.toJson()}, 201

@bp.route("/auth/logout", methods=["POST"])
@api_access()
def logout():
    tokens.revoke(g.api_token)
    return {"success": True}

@bp.route("/auth/me")
@api_access()
def me():
    return {"user": account_json(g.user)}

@bp.route("/auth/tokens")
@api_access()
def list_tokens():
    return {"tokens": [
        {**token.toJson(), "current": token.id == g.api_token.id} for token in tokens.user_tokens(g.user.id)
    ]}

@bp.route("/auth/tokens/<int:token_id>", methods=["DELETE"])
@api_access()
def revoke_token(token_id: int):
    token = next((token for token in tokens.user_tokens(g.user.id) if token.id == token_id), None)
    if token is None:
        return api_error(404, "not_found", "Token not found")
    tokens.revoke(token)
    return {"success": True}

# --- Library ---

@bp.route("/manga")
@api_access()
def manga_list():
    list_name = request.args.get("list", "all")
    if list_name not in library.LISTS:
        return api_error(400, "bad_request", f"list must be one of: {', '.join(library.LISTS)}")
    query = library.list_query(list_name, g.user.id, request.args.get("sort"))
    return paged_response(query, int_arg("offset", 0), int_arg("limit", batch_size(), 1, MAX_BATCH_SIZE))

@bp.route("/manga/search")
@api_access()
def manga_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return {"items": [], "offset": 0, "total": 0, "next_offset": None}
    query = library.search_query(q, request.args.get("sort"))
    return paged_response(query, int_arg("offset", 0), int_arg("limit", batch_size(), 1, MAX_BATCH_SIZE))

@bp.route("/manga/random")
@api_access()
def manga_random():
    manga_id = library.random_id(g.user.id, unread_only=request.args.get("unread") in ("1", "true"))
    if manga_id is None:
        return api_error(404, "not_found", "The library is empty")
    return {"id": manga_id}

@bp.route("/manga/<int:manga_id>")
@api_access()
def manga_info(manga_id: int):
    manga = get_manga_or_404(manga_id)
    page_counts = library.chapter_page_counts(manga.id)
    user_data = db.UserMangaData.getOrCreate(g.user.id, manga)
    total_chapters = len(manga.chapters)

    return {
        **manga.toJson(),
        "cover_url": cover_url(manga.id),
        "tags": sorted((tag.toJson() for tag in manga.manga_metadata.tags), key=lambda tag: tag["tag"]),
        "chapters": [
            {"number": chapter.number, "title": chapter.title, "page_count": page_counts.get(chapter.number, 0)}
            for chapter in manga.chapters
        ],
        "user": user_data.toJson(),
        # Only the owner sees where files live on the server
        "path": manga.path if Access.fromString(g.user.role) == Access.OWNER else None,
        "progress": library.progress_fraction(user_data, total_chapters, page_counts.get(user_data.current_chapter, 0)),
        # Where "Continue reading" should open. New readers start at the beginning.
        "resume": {
            "chapter": user_data.current_chapter if not user_data.new else 1,
            "page": user_data.current_page if not user_data.new else 1,
        },
    }

@bp.route("/manga/<int:manga_id>/chapters/<int:chapter_number>")
@api_access()
def chapter_info(manga_id: int, chapter_number: int):
    manga = get_manga_or_404(manga_id)
    chapter = db.Chapter.fromManga(manga, chapter_number)
    if chapter is None:
        return api_error(404, "not_found", f"Chapter {chapter_number} not found")

    chapter_numbers = [c.number for c in manga.chapters]
    index = chapter_numbers.index(chapter.number)
    page_numbers = sorted(page.number for page in chapter.pages)
    return {
        "manga_id": manga.id,
        "manga_title": manga.title,
        "number": chapter.number,
        "title": chapter.title,
        "page_count": len(page_numbers),
        "previous_chapter": chapter_numbers[index - 1] if index > 0 else None,
        "next_chapter": chapter_numbers[index + 1] if index + 1 < len(chapter_numbers) else None,
        "pages": [
            {"number": number, "image_url": page_image_url(manga.id, chapter.number, number)} for number in page_numbers
        ],
    }

@bp.route("/manga/<int:manga_id>/progress", methods=["PUT"])
@api_access()
def save_progress(manga_id: int):
    manga = get_manga_or_404(manga_id)
    body = json_body()
    chapter, page = body.get("chapter"), body.get("page")
    if not isinstance(chapter, int) or not isinstance(page, int):
        return api_error(400, "bad_request", "chapter and page must be numbers")

    user_data = library.save_progress(g.user.id, manga, chapter, page)
    if user_data is None:
        return api_error(404, "not_found", f"Chapter {chapter} page {page} not found")
    return {"user": user_data.toJson()}

@bp.route("/manga/<int:manga_id>/state", methods=["PUT"])
@api_access()
def update_state(manga_id: int):
    manga = get_manga_or_404(manga_id)
    body = json_body()
    user_data = library.update_state(
        g.user.id, manga,
        is_read=optional_bool(body, "is_read"),
        reset=body.get("reset") is True,
        is_favorite=optional_bool(body, "is_favorite"),
        is_queued=optional_bool(body, "is_queued"),
    )
    return {"user": user_data.toJson()}

@bp.route("/tags")
@api_access()
def tags():
    return {"tags": [tag.toJson() for tag in db.session.scalars(select(ContentTag).order_by(ContentTag.tag))]}

# --- Images ---

@bp.route("/manga/<int:manga_id>/cover")
@api_access()
def cover(manga_id: int):
    """A small JPEG thumbnail of the first page, or the original image with ?full=1."""
    manga = get_manga_or_404(manga_id)
    if manga_views.HIDE_MANGA or not manga.chapters:
        return manga_views.IMAGE_404()

    first_chapter = manga.chapters[0].number
    if request.args.get("full") not in ("1", "true"):
        cover_page = db.Page.fromChapter(manga.chapters[0], 1)
        thumbnail = thumbnails.cover_thumbnail_path(manga, cover_page, thumbnail_cache_dir()) if cover_page else None
        if thumbnail is not None:
            return send_file(thumbnail, mimetype="image/jpeg", max_age=IMAGE_MAX_AGE)

    return manga_views.image(manga_id=manga.id, chapter_number=first_chapter, page_number=1)

@bp.route("/manga/<int:manga_id>/chapters/<int:chapter_number>/pages/<int:page_number>/image")
@api_access()
def page_image(manga_id: int, chapter_number: int, page_number: int):
    return manga_views.image(manga_id=manga_id, chapter_number=chapter_number, page_number=page_number)

# Account, user, tag, manga and library management routes
from . import api_v1_admin  # noqa: E402,F401
