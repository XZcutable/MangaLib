"""Series details (summary, writer, genres...): what the API shows, what can be edited, importing them
from ComicInfo.xml during scans, and writing approved edits back into the files."""
import json, os
from typing import Optional

from sqlalchemy import func, select

from ..database import db
from ..models import Manga, MangaMetadata, MetadataSuggestion, User
from . import comicinfo, jobs

TEXT_LIMITS = {
    "title": 300,
    "summary": 5000,
    "writer": 200,
    "artist": 200,
    "publisher": 200,
    "age_rating": 50,
    "web": 500,
    "format": 50,
    "language": 20,
}
FIELDS = (*TEXT_LIMITS, "genres", "year", "reading_direction")
FIRST_VOLUME_ONLY = ("summary", "year")
MAX_GENRES, MAX_GENRE_LENGTH = 30, 50

def current(manga: Manga) -> dict:
    meta = manga.manga_metadata
    return {
        "title": manga.title,
        "summary": meta.summary,
        "writer": meta.writer,
        "artist": meta.artist,
        "publisher": meta.publisher,
        "genres": [genre.strip() for genre in (meta.genres or "").split(",") if genre.strip()],
        "year": manga.release_year,
        "language": meta.language or None,
        "age_rating": meta.age_rating,
        "web": meta.web,
        "format": meta.format,
        "reading_direction": meta.reading_direction,
    }

WEBTOON_WORDS = ("webtoon", "long strip", "vertical scroll")

def reading_hint(manga: Manga) -> dict:
    """How the reader should open this series by default, from its details. None means no opinion:
    the app then decides from the page shapes and the user's settings."""
    meta = manga.manga_metadata
    words = " ".join([meta.format or "", meta.genres or ""]).lower()
    return {
        "mode": "vertical" if any(word in words for word in WEBTOON_WORDS) else None,
        "direction": meta.reading_direction,
    }

def clean(changes) -> tuple[Optional[dict], Optional[str]]:
    """Checks edited fields. Returns (cleaned changes, None) or (None, error message).
    Empty strings and lists become None, which clears the field."""
    if not isinstance(changes, dict) or not changes:
        return None, "changes must be an object of fields to change"
    cleaned = {}
    for field, value in changes.items():
        if field not in FIELDS:
            return None, f"'{field}' can't be edited"
        if field in TEXT_LIMITS:
            if value is not None and not isinstance(value, str):
                return None, f"{field} must be text"
            value = (value or "").strip() or None
            if value and len(value) > TEXT_LIMITS[field]:
                return None, f"{field} is too long (at most {TEXT_LIMITS[field]} characters)"
            if field == "title" and value is None:
                return None, "Title can't be empty"
            if field == "web" and value and not value.lower().startswith(("http://", "https://")):
                return None, "web must be a link starting with http:// or https://"
        elif field == "genres":
            if value is None:
                value = []
            if not isinstance(value, list) or not all(isinstance(genre, str) for genre in value):
                return None, "genres must be a list of names"
            value = list(dict.fromkeys(genre.strip() for genre in value if genre.strip()))
            if len(value) > MAX_GENRES or any(len(genre) > MAX_GENRE_LENGTH or "," in genre for genre in value):
                return None, f"At most {MAX_GENRES} genres, each under {MAX_GENRE_LENGTH} characters with no commas"
        elif field == "year":
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or not 1000 <= value <= 9999):
                return None, "year must be a four-digit number"
        elif field == "reading_direction":
            if value not in (None, "ltr", "rtl"):
                return None, "reading_direction must be ltr, rtl or null"
        cleaned[field] = value
    return cleaned, None

def differences(manga: Manga, changes: dict) -> dict:
    """Only the fields that would actually change."""
    now = current(manga)
    return {field: value for field, value in changes.items() if now.get(field) != value}

def _apply_to_db(manga: Manga, fields: dict):
    meta = manga.manga_metadata
    for field, value in fields.items():
        if field == "title":
            manga.title = value
        elif field == "year":
            meta.year = value
            manga.release_year = value
        elif field == "genres":
            meta.genres = ", ".join(value) if value else None
        elif field == "language":
            meta.language = value or ""
        else:
            setattr(meta, field, value)

def import_from_files(manga: Manga) -> bool:
    """Fills in a newly scanned manga's details from ComicInfo.xml in its first volume, or in its folder.
    Never runs again once details have been checked or edited. Returns True if anything was found."""
    meta = manga.manga_metadata
    if meta is None or meta.metadata_source is not None:
        return False
    fields = {}
    for chapter in manga.chapters[:1]:
        if chapter.archive_type in (".cbz", ".zip"):
            fields = comicinfo.read_archive(chapter.path)
        elif chapter.archive_type is None:
            fields = comicinfo.read_folder(chapter.path)
    if not fields and os.path.isdir(manga.path):
        fields = comicinfo.read_folder(manga.path)

    # The folder or file name stays the title unless someone edits it
    fields.pop("title", None)
    if fields:
        _apply_to_db(manga, fields)
        meta.metadata_source = "file"
    else:
        meta.metadata_source = "none"
    return bool(fields)

def fill_missing_from_files():
    """Startup backfill: reads ComicInfo.xml for manga scanned before details were tracked."""
    manga_list = db.session.scalars(
        select(Manga).join(MangaMetadata).where(MangaMetadata.metadata_source.is_(None))
    ).all()
    found = sum(1 for manga in manga_list if import_from_files(manga))
    if manga_list:
        db.session.commit()
    if found:
        print(f"Read series details from ComicInfo.xml for {found} manga")

def write_targets(manga: Manga) -> tuple[list[str], list[str]]:
    """(archives, folders) that get the series' ComicInfo.xml. PDFs aren't changed."""
    archives = [chapter.path for chapter in manga.chapters if chapter.archive_type in (".cbz", ".zip")]
    folders = [manga.path] if os.path.isdir(manga.path) and any(c.archive_type is None for c in manga.chapters) else []
    return archives, folders

def apply(manga: Manga, changes: dict) -> Optional[dict]:
    """Saves changes in the database and queues writing them into the files.
    Returns the job, or None when no files need changing. The caller commits."""
    _apply_to_db(manga, changes)
    manga.manga_metadata.metadata_source = "edited"
    db.session.flush()

    # Only the changed fields are written. Summary and year are per volume in ComicInfo.xml, so the
    # series' values go into the first volume only and the other volumes keep their own.
    fields = {field: value for field, value in current(manga).items() if field in changes}
    series_fields = {field: value for field, value in fields.items() if field not in FIRST_VOLUME_ONLY}
    archives, folders = write_targets(manga)
    writes = [(path, fields if index == 0 else series_fields) for index, path in enumerate(archives)]
    writes = [(path, values) for path, values in writes if values]
    folder_writes = [(path, fields) for path in folders]
    if not writes and not folder_writes:
        return None

    def work(job):
        for path, values in writes:
            comicinfo.write_archive(path, values)
            job["done"] += 1
        for path, values in folder_writes:
            comicinfo.write_folder(path, values)
            job["done"] += 1
        return f"Updated {job['done']} file{'s' if job['done'] != 1 else ''}"

    db.session.commit()
    return jobs.submit("metadata", manga.id, work, total=len(archives) + len(folders))

# --- Suggestions ---

def suggestion_json(suggestion: MetadataSuggestion, include_manga: bool = False) -> dict:
    data = {
        "id": suggestion.id,
        "manga_id": suggestion.manga_id,
        "user_id": suggestion.user_id,
        "changes": json.loads(suggestion.changes),
        "status": suggestion.status,
        "created": suggestion.created,
        "reviewed_when": suggestion.reviewed_when,
    }
    user = db.session.get(User, suggestion.user_id)
    data["username"] = user.username if user else None
    if include_manga:
        manga = db.session.get(Manga, suggestion.manga_id)
        data["manga_title"] = manga.title if manga else None
        data["current"] = {field: current(manga).get(field) for field in data["changes"]} if manga else {}
    return data

def pending_for(user_id: int, manga_id: int) -> Optional[MetadataSuggestion]:
    return db.session.scalar(
        select(MetadataSuggestion).where(
            MetadataSuggestion.user_id == user_id,
            MetadataSuggestion.manga_id == manga_id,
            MetadataSuggestion.status == "pending",
        )
    )

def suggest(user_id: int, manga: Manga, changes: dict) -> MetadataSuggestion:
    """Adds a suggestion, or replaces the user's pending one for this manga."""
    suggestion = pending_for(user_id, manga.id)
    if suggestion is None:
        suggestion = MetadataSuggestion(manga_id=manga.id, user_id=user_id, changes="{}", created=db.getDatetimeISONow())
        db.session.add(suggestion)
    suggestion.changes = json.dumps(changes)
    db.session.commit()
    return suggestion

def pending_count() -> int:
    return db.session.scalar(
        select(func.count()).select_from(MetadataSuggestion).where(MetadataSuggestion.status == "pending")
    )

def review(suggestion: MetadataSuggestion, reviewer_id: int, approve: bool) -> Optional[dict]:
    """Approves (applies) or rejects a suggestion. Returns the file-write job when one was started."""
    suggestion.status = "approved" if approve else "rejected"
    suggestion.reviewed_by = reviewer_id
    suggestion.reviewed_when = db.getDatetimeISONow()
    job = None
    if approve:
        manga = db.session.get(Manga, suggestion.manga_id)
        if manga is not None:
            changes = differences(manga, json.loads(suggestion.changes))
            if changes:
                job = apply(manga, changes)
    db.session.commit()
    return job
