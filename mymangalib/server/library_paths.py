from mymangalib.helpers import validate_string
from typing import Final


import os
from ..database import db
from ..models import Chapter, Manga, Path
from ..queries import QUERY_PATHS

from sqlalchemy import String, func, literal, or_, select, update

_PATHS: Final[set] = set()

#This is used when scaning for
def has_path(path: str) -> bool:
    validate_string(path)
    return db.session.scalars(QUERY_PATHS.where(Path.path == path)).one_or_none() is not None

def update_paths():
    _PATHS.clear()
    _PATHS.update(db.session.scalars(QUERY_PATHS).all())
    #[path[0] for path in Path.query.values(Path.path)]

def get_paths() -> set[str]: 
    return list(_PATHS)
    # return [path[0] for path in Path.query.values(Path.path)]

def add_path(path):
    validate_string(path)

    if has_path(path):
        raise ValueError("Path is already registered")
    elif not os.path.isdir(path):
        raise ValueError("Path is not a dir")
    else:
        path = Path(path=path)
        db.session.add(path)
        db.session.commit()
        update_paths()

def remove_path(path):
    q_path: Path = db.session.scalars(select(Path).where(Path.path == path)).one_or_none()
    if q_path is None:
        raise ValueError(f"'{path}' was not a path")
    else:
        db.session.delete(q_path)
        db.session.commit()
        update_paths()

# --- Moving folders ---
# Manga and chapters are stored with full paths (Manga.path, Chapter.path; pages only keep their file
# name). When files move, these rewrite the stored paths so the manga keep their ids, and with them
# reading progress, ratings, tags and read marks.

def normalize(path: str) -> str:
    """The form library folders are stored in: forward slashes, no trailing slash (except a root)."""
    path = os.path.normpath(str(path).strip()).replace("\\", "/")
    return path if path.endswith(":/") or path == "/" else path.rstrip("/")

def _under(column, folder: str):
    """Rows whose path is `folder` or inside it. The scanner joins names with os.path.join, so on
    Windows the part after a library folder can start with either slash."""
    if folder.endswith("/"):  # A drive or filesystem root
        return column.startswith(folder, autoescape=True)
    return or_(column == folder,
               column.startswith(folder + "/", autoescape=True),
               column.startswith(folder + "\\", autoescape=True))

def rewrite_prefix(old: str, new: str) -> int:
    """Points every manga and chapter stored under `old` to the same place under `new`, in the current
    transaction (the caller commits). Returns how many manga changed."""
    # What follows `old` in a stored path starts with a slash, except under a root like "D:/"
    start, prefix = len(old) + 1, new  # SQLite's substr counts from 1
    if old.endswith("/") and not new.endswith("/"):
        prefix = new + "/"
    elif new.endswith("/") and not old.endswith("/"):
        start += 1
    moved = 0
    for model in (Manga, Chapter):
        result = db.session.execute(
            update(model).where(_under(model.path, old))
            .values(path=literal(prefix, String).concat(func.substr(model.path, start, type_=String)))
            .execution_options(synchronize_session=False)
        )
        if model is Manga:
            moved = result.rowcount
    db.session.expire_all()
    return moved

def registered_as(folder: str):
    """The library folder entry for `folder`, however it was written when it was added."""
    folder = normalize(folder)
    return next((path for path in db.session.scalars(QUERY_PATHS) if normalize(path) == folder), None)

def manga_under(folder: str) -> list[Manga]:
    return list(db.session.scalars(select(Manga).where(_under(Manga.path, folder))))

def move_library(old: str, new: str) -> dict:
    """For a library folder whose files were moved (or mounted somewhere else): registers `new` in place
    of `old` and points its manga there. Nothing on disk changes."""
    old, new = normalize(old), normalize(new)
    if old == new:
        raise ValueError("The old and new folders are the same")
    registered = registered_as(old)
    if registered is None:
        raise ValueError(f"'{old}' isn't a library folder")
    if registered_as(new) is not None:
        raise ValueError(f"'{new}' is already a library folder")
    if not os.path.isdir(new):
        raise ValueError(f"'{new}' isn't a folder on the server")

    try:
        db.session.delete(db.session.get(Path, registered))
        if registered != old:  # Stored in another form (e.g. backslashes, from the classic settings page)
            rewrite_prefix(registered, old)
        db.session.add(Path(path=new))
        moved = rewrite_prefix(old, new)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        update_paths()
    missing = [manga.title for manga in manga_under(new) if not os.path.exists(manga.path)]
    return {"path": new, "moved": moved, "missing": len(missing), "missing_titles": missing[:20]}

def apply_configured_moves(app) -> None:
    """LIBRARY_MOVES in the config, {"old folder": "new folder"}: done once at startup, before the scan.
    A move that's already been done is skipped, so the setting can stay in place."""
    moves = app.config.get("LIBRARY_MOVES") or {}
    if not isinstance(moves, dict):
        print("LIBRARY_MOVES must map old folders to new ones, e.g. {\"/mnt/manga\": \"/var/manga\"}; ignored")
        return
    with app.app_context():
        update_paths()
        for old, new in moves.items():
            if registered_as(old) is None:
                continue  # Already moved, or never a library folder
            try:
                result = move_library(old, new)
            except ValueError as error:
                print(f"LIBRARY_MOVES: couldn't move '{old}' to '{new}': {error}")
                continue
            print(f"LIBRARY_MOVES: moved library folder '{old}' to '{new}' ({result['moved']} manga)")
            if result["missing"]:
                print(f"LIBRARY_MOVES: {result['missing']} manga weren't found in the new folder, "
                      f"e.g. {', '.join(result['missing_titles'][:3])}")