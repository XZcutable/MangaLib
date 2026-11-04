"""/api/v1 routes for managing the account, users, tags, manga and the library.

Admins manage users, tags and manga details. The owner also manages library folders,
scanning, deleting manga and server display settings, matching the classic UI's rules.
"""
import os

from flask import g, request
from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import api_access, api_error, rename_user, valid_password_pattern
from ..database import db
from ..enum import Access
from ..models import ContentTag, Manga, User, UserMangaData
from ..server import api as scanner, settings as library_settings, tokens, server_settings
from .api import valid_tag_pattern
from .api_v1 import account_json, bp, get_manga_or_404, json_body, optional_bool, thumbnail_cache_dir

def normalize_path(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/")

# --- Account ---

@bp.route("/auth/password", methods=["PUT"])
@api_access()
def change_password():
    body = json_body()
    current, new = body.get("current_password"), body.get("new_password")
    if not isinstance(current, str) or not isinstance(new, str):
        return api_error(400, "bad_request", "current_password and new_password are required")
    if not check_password_hash(g.user.password, current):
        return api_error(403, "wrong_password", "Your current password is incorrect")
    if not valid_password_pattern.search(new):
        return api_error(
            400,
            "weak_password",
            "Passwords need 6-20 characters with at least one number, uppercase letter, lowercase letter and symbol",
        )

    g.user.password = generate_password_hash(new)
    db.session.commit()
    # Other devices have to log in again with the new password
    for token in tokens.user_tokens(g.user.id):
        if token.id != g.api_token.id:
            db.session.delete(token)
    db.session.commit()
    return {"success": True}

@bp.route("/auth/username", methods=["PUT"])
@api_access()
def change_username():
    username = json_body().get("username")
    if not isinstance(username, str):
        return api_error(400, "bad_request", "Username is required")
    error = rename_user(g.user, username)
    if error == "That username is taken":
        return api_error(409, "username_taken", error)
    if error is not None:
        return api_error(400, "bad_username", error)
    return {"user": account_json(g.user)}

# --- Users (admin) ---

def user_admin_json(user: User) -> dict:
    return {**user.toJson(), "date_created": user.date_created}

@bp.route("/admin/users")
@api_access(Access.ADMIN)
def list_users():
    users = db.session.scalars(select(User).order_by(User.approved, User.id)).all()
    return {"users": [user_admin_json(user) for user in users]}

@bp.route("/admin/users/<int:user_id>", methods=["DELETE"])
@api_access(Access.ADMIN)
def delete_user(user_id: int):
    """Removes an account with its reading history and logins. Used to reject sign-ups."""
    user = db.session.get(User, user_id)
    if user is None:
        return api_error(404, "not_found", "User not found")
    if user.id == g.user.id or Access.fromString(user.role) == Access.OWNER:
        return api_error(403, "forbidden", "That account can't be deleted")
    if user.approved and Access.fromString(g.user.role) != Access.OWNER:
        return api_error(403, "forbidden", "Only the owner can delete approved accounts")

    for token in tokens.user_tokens(user.id):
        db.session.delete(token)
    db.session.query(UserMangaData).filter(UserMangaData.user_id == user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return {"success": True}

@bp.route("/admin/users/<int:user_id>", methods=["PUT"])
@api_access(Access.ADMIN)
def update_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return api_error(404, "not_found", "User not found")
    if user.id == g.user.id:
        return api_error(403, "forbidden", "You can't change your own access")
    if Access.fromString(user.role) == Access.OWNER:
        return api_error(403, "forbidden", "The owner account can't be changed")

    body = json_body()
    approved = optional_bool(body, "approved")
    must_change_username = optional_bool(body, "must_change_username")
    role = body.get("role")

    if must_change_username is not None:
        # Admins can make anyone below the owner pick a new name, e.g. one that's offensive or confusing
        user.must_change_username = must_change_username
    if role is not None:
        # Only the owner hands out roles, and there is only ever one owner
        if Access.fromString(g.user.role) != Access.OWNER:
            return api_error(403, "forbidden", "Only the owner can change roles")
        new_role = Access.fromString(role)
        if new_role in (Access.NONE, Access.OWNER):
            return api_error(400, "bad_request", "Role must be user, moderator or admin")
        user.role = new_role.toString()
    if approved is not None:
        user.approved = approved
        if not approved:
            # Un-approving signs the user out everywhere
            for token in tokens.user_tokens(user.id):
                db.session.delete(token)
    db.session.commit()
    return {"user": user_admin_json(user)}

# --- Tags (admin) ---

@bp.route("/tags", methods=["POST"])
@api_access(Access.ADMIN)
def create_tag():
    body = json_body()
    name = body.get("tag")
    nsfw = body.get("nsfw") is True
    if not isinstance(name, str) or not valid_tag_pattern.fullmatch(name.strip().lower()):
        return api_error(400, "bad_request", "Tags are lowercase words separated by single spaces")
    name = name.strip().lower()

    tag = db.session.get(ContentTag, name)
    if tag is None:
        tag = ContentTag(tag=name, nsfw=nsfw)
        db.session.add(tag)
    elif tag.nsfw == nsfw:
        return api_error(409, "tag_exists", f"Tag '{name}' already exists")
    else:
        tag.nsfw = nsfw
    db.session.commit()
    return {"tag": tag.toJson()}, 201

@bp.route("/tags/<path:name>", methods=["DELETE"])
@api_access(Access.ADMIN)
def delete_tag(name: str):
    tag = db.session.get(ContentTag, name)
    if tag is None:
        return api_error(404, "not_found", "Tag not found")
    db.session.delete(tag)
    db.session.commit()
    return {"success": True}

@bp.route("/manga/<int:manga_id>/tags", methods=["PUT"])
@api_access(Access.ADMIN)
def set_manga_tags(manga_id: int):
    manga = get_manga_or_404(manga_id)
    names = json_body().get("tags")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        return api_error(400, "bad_request", "tags must be a list of tag names")

    found = db.session.scalars(select(ContentTag).where(ContentTag.tag.in_(names))).all()
    missing = set(names) - {tag.tag for tag in found}
    if missing:
        return api_error(400, "unknown_tag", f"Unknown tags: {', '.join(sorted(missing))}")

    manga.manga_metadata.tags.clear()
    manga.manga_metadata.tags.extend(found)
    db.session.commit()
    return {"tags": sorted((tag.toJson() for tag in found), key=lambda tag: tag["tag"])}

# --- Manga (admin and owner) ---

@bp.route("/manga/<int:manga_id>", methods=["PATCH"])
@api_access(Access.ADMIN)
def edit_manga(manga_id: int):
    """{"title": "New title"} renames it. {"title": null} goes back to the folder or file name."""
    manga = get_manga_or_404(manga_id)
    body = json_body()
    if "title" in body:
        title = body["title"]
        if title is None:
            manga.title = manga.original_title
        elif isinstance(title, str) and title.strip():
            manga.title = title.strip()
        else:
            return api_error(400, "bad_request", "Title can't be empty")
    db.session.commit()
    return {"id": manga.id, "title": manga.title, "original_title": manga.original_title}

@bp.route("/manga/<int:manga_id>", methods=["DELETE"])
@api_access(Access.OWNER)
def delete_manga(manga_id: int):
    """Removes the manga from the library. Files on disk are not touched, so a later scan adds it back."""
    manga = get_manga_or_404(manga_id)
    db.session.delete(manga)
    db.session.commit()
    db.Manga.update_manga_count()
    try:
        os.remove(os.path.join(thumbnail_cache_dir(), f"{manga_id}.jpg"))
    except OSError:
        pass
    return {"success": True}

@bp.route("/manga/<int:manga_id>/rescan", methods=["POST"])
@api_access(Access.OWNER)
def rescan_manga(manga_id: int):
    manga = get_manga_or_404(manga_id)
    db.session.begin_nested()
    success, error = scanner.rescan_manga(manga)
    if not success:
        db.session.rollback()
        return api_error(422, "rescan_failed", f"Couldn't rescan: {error}")
    db.session.commit()
    return {"success": True, "total_chapters": len(manga.chapters)}

# --- Library folders and scanning (owner) ---

@bp.route("/library")
@api_access(Access.OWNER)
def library():
    return {"paths": sorted(library_settings.get_paths())}

@bp.route("/library/paths", methods=["POST"])
@api_access(Access.OWNER)
def add_library_path():
    path = json_body().get("path")
    if not isinstance(path, str) or not path.strip():
        return api_error(400, "bad_request", "path is required")
    try:
        library_settings.add_path(normalize_path(path.strip()))
    except ValueError as error:
        return api_error(400, "bad_path", str(error))
    return {"paths": sorted(library_settings.get_paths())}, 201

@bp.route("/library/paths", methods=["DELETE"])
@api_access(Access.OWNER)
def remove_library_path():
    path = request.args.get("path", "")
    try:
        library_settings.remove_path(normalize_path(path))
    except ValueError as error:
        return api_error(404, "not_found", str(error))
    return {"paths": sorted(library_settings.get_paths())}

@bp.route("/library/browse")
@api_access(Access.OWNER)
def browse_folders():
    """Folders on the server, for picking a library folder. No dir lists the drives or root."""
    folder = (request.args.get("dir") or "").strip()
    if not folder or folder == "/":
        return {"dir": "", "parent": None, "folders": [
            {"name": name, "path": normalize_path(name if os.name == "nt" else f"/{name}")}
            for name in scanner.getRootFolders()
        ]}

    folder = normalize_path(folder)
    if os.name == "nt" and folder.endswith(":"):
        folder += "/"
    if not os.path.isdir(folder):
        return api_error(404, "not_found", f"'{folder}' isn't a folder on the server")

    parent = os.path.dirname(folder.rstrip("/")) if folder not in ("/",) else None
    if os.name == "nt" and folder.endswith(":/"):
        parent = ""
    names = sorted(scanner.lsDirs(folder), key=str.casefold)
    return {
        "dir": folder,
        "parent": normalize_path(parent) if parent else parent,
        "folders": [{"name": name, "path": normalize_path(os.path.join(folder, name))} for name in names],
    }

@bp.route("/library/scan", methods=["POST"])
@api_access(Access.OWNER)
def scan():
    """Scans every library folder, or one with {"path": ...}, for new manga and new chapters."""
    paths = library_settings.get_paths()
    path = json_body().get("path")
    if path is not None:
        if path not in paths:
            return api_error(404, "not_found", "That folder isn't in the library")
        paths = [path]
    return scanner.scan_library(paths)

# --- Server settings (owner) ---

@bp.route("/server/config")
@api_access(Access.OWNER)
def get_config():
    return server_settings.as_json()

@bp.route("/server/config", methods=["PUT"])
@api_access(Access.OWNER)
def update_config():
    """Any of allow_new_users, auto_approve_new_users, hide_manga, hide_titles (true/false) and site_name
    (text; empty goes back to config.toml). Saved, so they survive restarts."""
    body = json_body()
    for key, name in server_settings.EDITABLE_TEXT.items():
        value = body.get(name)
        if value is not None and not isinstance(value, str):
            return api_error(400, "bad_request", f"{name} must be text")
        if isinstance(value, str):
            error = server_settings.set_text(key, value)
            if error is not None:
                return api_error(400, "bad_request", error)
    for key, name in server_settings.EDITABLE.items():
        value = optional_bool(body, name)
        if value is not None:
            server_settings.set(key, value)
    return get_config()
