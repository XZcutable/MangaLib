"""JSON API for external clients (the mobile app and the new web front end).

Every route takes and returns JSON, authenticates with `Authorization: Bearer <token>`
(from POST /auth/login), and reports errors as {"error": {"code", "message"}}.
Image routes also accept the token as ?t= because <img> tags can't send headers.
"""
import hashlib, json, os

from flask import Flask, Blueprint, request, g, current_app, url_for, abort, send_file, got_request_exception
from werkzeug.exceptions import HTTPException
from sqlalchemy import select, func
from flask_cors import CORS

from ..auth import (API_V1_PREFIX, INVITE_MESSAGES, api_access, api_error, check_credentials, check_invite,
                    register_account, registration_rules, get_owner)
from ..database import db
from ..enum import Access
from ..models import Manga, ContentTag, User
from ..server import library, server_settings, tokens, thumbnails, jobs, repack, updater, invites, languages
from ..server import metadata as series_metadata
from ..server import feedback, logbuffer
from . import manga as manga_views
from ..version import __version__

bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Bump when routes or fields are added, so the app can tell what an older server lacks.
# 2: ratings, chapter read marks, series details and suggestions, crunch/unpack, reading hints.
# 3: server updates (/admin/server/update), restart_in in /server/info.
# 4: moving library folders (PUT /library/paths) and series (POST /manga/<id>/move).
# 5: crunching every series (POST /library/crunch/preview, POST /library/crunch) and its leftover files
#    (GET /library/leftovers, POST /library/leftovers/delete).
# 6: invites (/invites), public_url in /server/info and /server/config, can_invite in /auth/me.
# 7: the search language (tag:a|b, nsfw:, language:, is:, -), languages in /server/info, language
#    limited to the fixed codes.
# 8: feedback (/feedback, /admin/feedback), pending_feedback in /auth/me.
API_VERSION = 8
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
         allow_headers=["Authorization", "Content-Type"], methods=["GET", "POST", "PUT", "PATCH", "DELETE"])

    def log_unhandled_error(sender, exception, **extra):
        # Kept in the log buffer, so a bug report sent soon after includes it
        logbuffer.logger("server").error("%s %s failed", request.method, request.path, exc_info=exception)
    # weak=False: blinker would otherwise drop this local function once init_app returns
    got_request_exception.connect(log_unhandled_error, app, weak=False)

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

def api_path(endpoint: str, **values) -> str:
    """A path from the server's base, e.g. /api/v1/manga/1/cover, without a sub-path the server is reached at.
    Clients add it to the server address they use (which includes the sub-path), so it isn't counted twice."""
    path = url_for(endpoint, **values)
    return path[len(request.script_root):] if request.script_root and path.startswith(request.script_root) else path

def cover_url(manga_id: int) -> str:
    return api_path("api_v1.cover", manga_id=manga_id)

def page_image_url(manga_id: int, chapter_number: int, page_number: int, chapter_path: str) -> str:
    """Images are cached by URL for days. A crunch, unpack or move can give a chapter number to different
    files, so the URL carries a short key of the chapter's path: a cached page never shows up for the wrong chapter."""
    key = hashlib.sha1(chapter_path.encode("utf-8")).hexdigest()[:8]
    return api_path("api_v1.page_image", manga_id=manga_id, chapter_number=chapter_number, page_number=page_number, v=key)

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
            "rating": state.get("rating", library.EMPTY_RATING),
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
    # Admins can always invite people; everyone else only while registration is open
    data["can_invite"] = invites.can_create(user)
    if data["is_admin"]:
        data["pending_users"] = db.session.scalar(select(func.count()).select_from(User).where(~User.approved))
        data["pending_suggestions"] = series_metadata.pending_count()
        data["pending_feedback"] = feedback.pending_count(user)
    if data.get("is_owner"):
        # For the badge on Settings: a newer server version is downloaded (or found)
        update = updater.get().as_json()
        data["server_update"] = {
            "status": update["status"],
            "version": update["staged_version"] or (update["latest"] or {}).get("version"),
        }
    return data

# --- Server ---

@bp.route("/server/info")
def server_info():
    needs_setup = get_owner() is None
    return {
        # Always "myMangaLib": the app checks it to know the address is a myMangaLib server
        "name": "myMangaLib",
        # The name to show people, which the owner can change
        "site_name": server_settings.site_name(),
        "version": __version__,
        "api_version": API_VERSION,
        "needs_setup": needs_setup,
        "registration_open": needs_setup or bool(current_app.config.get("ALLOW_NEW_USERS")),
        # The address the owner wants shared in invite links, or "" to share the one the app is using
        "public_url": server_settings.public_url(),
        "hide_titles": manga_views.HIDE_TITLES,
        # Where the classic web interface is: /classic/ when this server also serves the new one
        "classic_ui_path": current_app.config.get("CLASSIC_UI_PATH", "/"),
        # Seconds until the server restarts into an update, so open pages can show a notice
        "restart_in": updater.get().restart_in(),
        # The choices for a series' language: search values and the details editor
        "languages": languages.LANGUAGES,
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

    invite = None
    if body.get("invite"):
        invite, invite_error = check_invite(body.get("invite"))
        if invite_error is not None:
            return api_error(404 if invite_error == "invite_invalid" else 403, invite_error, INVITE_MESSAGES[invite_error])

    registration_open, auto_approve = registration_rules(invite)
    user, error = register_account(username.strip(), password, registration_open, auto_approve, invite)
    if error is not None:
        status, code = (403, "registration_closed") if error == 'Registration is closed' else (409, "username_taken")
        return api_error(status, code, error)
    return {"user": user.toJson()}, 201

# --- Invites ---
# Shared as <server>/join?code=..., as a link or QR code. See server/invites.py for who can use them.

@bp.route("/invites/<code>")
def invite_info(code: str):
    """Public: lets the join page show the site name and whether the account will need approval."""
    invite = invites.find(code)
    if invite is None:
        return api_error(404, "invite_invalid", INVITE_MESSAGES["invite_invalid"])
    status = invites.status(invite)
    data = invites.as_json(invite)
    return {
        "valid": status == "active",
        "status": status,
        "message": INVITE_MESSAGES.get(status),
        "site_name": server_settings.site_name(),
        "invited_by": data["created_by"]["username"],
        "approved_on_join": data["approved_on_join"],
        "expires": invite.expires,
    }

@bp.route("/invites")
@api_access()
def list_invites():
    """Your own invites. Admins see everyone's."""
    return {"invites": [invites.as_json(invite) for invite in invites.listed(g.user)], "can_invite": invites.can_create(g.user)}

@bp.route("/invites", methods=["POST"])
@api_access()
def create_invite():
    """expires_days (1-30, default 7) and max_uses (1-100, or null for any number; default 1).
    The code is only returned here."""
    if not invites.can_create(g.user):
        return api_error(403, "registration_closed", "Registration is closed, so only admins can invite people")
    body = json_body()

    days = body.get("expires_days", invites.DEFAULT_DAYS)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= invites.MAX_DAYS:
        return api_error(400, "bad_request", f"expires_days must be a whole number from 1 to {invites.MAX_DAYS}")
    max_uses = body.get("max_uses", 1)
    if max_uses is not None and (isinstance(max_uses, bool) or not isinstance(max_uses, int) or not 1 <= max_uses <= invites.MAX_USES):
        return api_error(400, "bad_request", f"max_uses must be a whole number from 1 to {invites.MAX_USES}, or null")

    invite, code = invites.create(g.user, days, max_uses)
    return {"invite": invites.as_json(invite), "code": code}, 201

@bp.route("/invites/<int:invite_id>", methods=["DELETE"])
@api_access()
def delete_invite(invite_id: int):
    """Cancels an invite. Your own, or anyone's for admins."""
    invite = db.session.get(invites.Invite, invite_id)
    if invite is None or not invites.can_delete(g.user, invite):
        return api_error(404, "not_found", "Invite not found")
    invites.delete(invite)
    return {"success": True}

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
    read = library.read_chapters(g.user.id, manga.id)

    return {
        **manga.toJson(),
        "cover_url": cover_url(manga.id),
        "tags": sorted((tag.toJson() for tag in manga.manga_metadata.tags), key=lambda tag: tag["tag"]),
        "chapters": [
            {
                "number": chapter.number,
                "title": chapter.title,
                "page_count": page_counts.get(chapter.number, 0),
                "is_read": chapter.number in read,
                "format": repack.chapter_format(chapter),
            }
            for chapter in manga.chapters
        ],
        "user": user_data.toJson(),
        "rating": {"mine": user_data.rating, **library.rating_summary(manga.id)},
        "metadata": series_metadata.current(manga),
        "reading_hint": series_metadata.reading_hint(manga),
        # Owner tools: what can be crunched or unpacked, and any conversion running now
        "repack": {
            "crunchable": len(repack.crunchable(manga)),
            "unpackable": len(repack.unpackable(manga)),
            "job": jobs.active_for(manga.id),
        } if Access.fromString(g.user.role) == Access.OWNER else None,
        "my_suggestion": suggestion_or_none(g.user.id, manga.id),
        # Only the owner sees where files live on the server
        "path": manga.path if Access.fromString(g.user.role) == Access.OWNER else None,
        "progress": library.progress_fraction(user_data, total_chapters, page_counts.get(user_data.current_chapter, 0)),
        # Where "Continue reading" should open. New readers start at the beginning.
        "resume": {
            "chapter": user_data.current_chapter if not user_data.new else 1,
            "page": user_data.current_page if not user_data.new else 1,
        },
    }

def suggestion_or_none(user_id: int, manga_id: int):
    suggestion = series_metadata.pending_for(user_id, manga_id)
    return series_metadata.suggestion_json(suggestion) if suggestion else None

@bp.route("/manga/<int:manga_id>/metadata/suggestions", methods=["POST"])
@api_access()
def suggest_metadata(manga_id: int):
    """{"changes": {"summary": "...", "genres": ["Action"]}} proposes new series details for an admin to review.
    A second suggestion for the same manga replaces the user's pending one."""
    manga = get_manga_or_404(manga_id)
    changes, problem = series_metadata.clean(json_body().get("changes"))
    if problem:
        return api_error(400, "bad_request", problem)
    changes = series_metadata.differences(manga, changes)
    if not changes:
        return api_error(400, "nothing_changed", "Those details are already set")
    suggestion = series_metadata.suggest(g.user.id, manga, changes)
    return {"suggestion": series_metadata.suggestion_json(suggestion)}, 201

@bp.route("/manga/<int:manga_id>/metadata/suggestions/mine", methods=["DELETE"])
@api_access()
def withdraw_suggestion(manga_id: int):
    suggestion = series_metadata.pending_for(g.user.id, manga_id)
    if suggestion is None:
        return api_error(404, "not_found", "No pending suggestion")
    db.session.delete(suggestion)
    db.session.commit()
    return {"success": True}

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
            {"number": number, "image_url": page_image_url(manga.id, chapter.number, number, chapter.path)} for number in page_numbers
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
    extra = {}
    if "rating" in body:
        if not library.valid_rating(body["rating"]):
            return api_error(400, "bad_request", f"rating must be a whole number from {library.RATING_MIN} to {library.RATING_MAX}, or null")
        extra["rating"] = body["rating"]
    user_data = library.update_state(
        g.user.id, manga,
        is_read=optional_bool(body, "is_read"),
        reset=body.get("reset") is True,
        is_favorite=optional_bool(body, "is_favorite"),
        is_queued=optional_bool(body, "is_queued"),
        **extra,
    )
    return {"user": user_data.toJson(), "rating": {"mine": user_data.rating, **library.rating_summary(manga.id)}}

@bp.route("/manga/<int:manga_id>/chapters/state", methods=["PUT"])
@api_access()
def update_chapters_state(manga_id: int):
    """{"chapters": [1, 2], "is_read": true} marks those chapters read (or unread)."""
    manga = get_manga_or_404(manga_id)
    body = json_body()
    numbers, is_read = body.get("chapters"), body.get("is_read")
    if (not isinstance(numbers, list) or not numbers or not isinstance(is_read, bool)
            or not all(isinstance(n, int) and not isinstance(n, bool) for n in numbers)):
        return api_error(400, "bad_request", "chapters must be a list of chapter numbers and is_read true or false")
    user_data = library.set_chapters_read(g.user.id, manga, numbers, is_read)
    if user_data is None:
        return api_error(404, "not_found", "One of those chapters doesn't exist")
    return {"user": user_data.toJson(), "read_chapters": sorted(library.read_chapters(g.user.id, manga.id))}

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

# --- Feedback ---
# Bug reports, ideas and content requests (server/feedback.py). The owner's inbox is in api_v1_admin.

def feedback_attachment_url(item, attachment) -> str:
    return api_path("api_v1.feedback_attachment", feedback_id=item.id, attachment_id=attachment.id)

def feedback_detail(item) -> dict:
    return feedback.feedback_json(item, g.user, feedback_attachment_url, detail=True)

def visible_feedback_or_error(feedback_id: int):
    """(item, None), or (None, a 404) when it doesn't exist or isn't this user's to see."""
    item = db.session.get(feedback.Feedback, feedback_id)
    if item is None or not feedback.can_view(g.user, item):
        return None, api_error(404, "not_found", "Feedback not found")
    return item, None

@bp.route("/feedback", methods=["POST"])
@api_access()
def send_feedback():
    """JSON, or multipart/form-data with the JSON in a `data` field and up to 3 `screenshots` files.
    Fields: kind, title, body, steps, expected, actual (bugs), manga_id and chapter (content_problem),
    client_log (the app's recent log, bugs only) and context (app version, platform, screen...)."""
    if request.mimetype == "multipart/form-data":
        try:
            body = json.loads(request.form.get("data") or "{}")
        except ValueError:
            return api_error(400, "bad_request", "data must be JSON")
        body = body if isinstance(body, dict) else {}
        files = request.files.getlist("screenshots")
    else:
        body, files = json_body(), []
    if body.get("kind") != "bug":
        body.pop("client_log", None)

    item, problem = feedback.create(g.user, body, files, {
        "server_version": __version__,
        "api_version": API_VERSION,
        "server_user_agent": request.user_agent.string[:300],
    })
    if problem == "too_many":
        return api_error(429, "too_many_feedback",
                         f"You can send up to {feedback.MAX_PER_DAY} reports a day. Try again tomorrow.")
    if problem:
        return api_error(400, "bad_request", problem)
    return {"feedback": feedback_detail(item)}, 201

@bp.route("/feedback/mine")
@api_access()
def my_feedback():
    return {"feedback": [feedback.feedback_json(item, g.user) for item in feedback.list_for_user(g.user)]}

@bp.route("/feedback/<int:feedback_id>")
@api_access()
def feedback_item(feedback_id: int):
    item, error = visible_feedback_or_error(feedback_id)
    return error or {"feedback": feedback_detail(item)}

@bp.route("/feedback/<int:feedback_id>/comments", methods=["POST"])
@api_access()
def comment_feedback(feedback_id: int):
    """{"body": "..."} adds a reply. When the sender answers a "needs info" question, the item goes back to new."""
    item, error = visible_feedback_or_error(feedback_id)
    if error:
        return error
    _, problem = feedback.comment(item, g.user, json_body().get("body"))
    if problem:
        return api_error(400, "bad_request", problem)
    return {"feedback": feedback_detail(item)}, 201

@bp.route("/feedback/<int:feedback_id>", methods=["DELETE"])
@api_access()
def delete_feedback(feedback_id: int):
    """The sender can withdraw an item until someone has looked at it; staff can always delete."""
    item, error = visible_feedback_or_error(feedback_id)
    if error:
        return error
    if not feedback.is_staff_for(g.user, item) and item.status != "new":
        return api_error(403, "forbidden", "This has already been looked at, so it can't be withdrawn")
    feedback.delete(item)
    return {"success": True}

@bp.route("/feedback/<int:feedback_id>/attachments/<int:attachment_id>")
@api_access()
def feedback_attachment(feedback_id: int, attachment_id: int):
    item, error = visible_feedback_or_error(feedback_id)
    if error:
        return error
    attachment = db.session.get(feedback.FeedbackAttachment, attachment_id)
    if attachment is None or attachment.feedback_id != item.id:
        return api_error(404, "not_found", "Attachment not found")
    path = feedback.attachment_path(attachment)
    if not os.path.isfile(path):
        return api_error(404, "not_found", "The file is missing on the server")
    return send_file(path, mimetype=attachment.content_type, max_age=IMAGE_MAX_AGE)

# Account, user, tag, manga and library management routes
from . import api_v1_admin  # noqa: E402,F401
