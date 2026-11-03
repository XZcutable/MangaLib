"""Library queries and per-user reading state, shared by the old /api routes and /api/v1."""
from typing import Optional

from sqlalchemy import Select, select, func

from ..database import db
from ..models import Manga, Chapter, Page, UserMangaData
from ..constants import SQL
from ..quries import QUERY_FAVORITES, QUERY_HISTORY, QUERY_QUEUE
from .search import create_search_query

# "latest" is "all" newest first. History, favorites and queued default to most recent first.
# "random" ignores sort and paging gives a new shuffle each time. "unread" is everything the user hasn't finished.
LISTS = ("all", "latest", "history", "favorites", "queued", "unread", "random")
DEFAULT_SORT = {"all": "asc", "latest": "desc", "history": "desc", "favorites": "desc", "queued": "desc", "unread": "asc", "random": "asc"}

def list_query(list_name: str, user_id: int, sort: Optional[str] = None) -> Select:
    """Returns a (id, title) query for one of LISTS. Raises ValueError for an unknown list."""
    if list_name not in LISTS:
        raise ValueError(f"Unknown list '{list_name}'")
    sort = sort if sort in SQL.ORDER else DEFAULT_SORT[list_name]

    if list_name in ("all", "latest"):
        return select(Manga.id, Manga.title).order_by(SQL.ORDER[sort](Manga.id))
    elif list_name == "random":
        return select(Manga.id, Manga.title).order_by(func.random())
    elif list_name == "unread":
        return (
            select(Manga.id, Manga.title)
            .outerjoin(UserMangaData, (UserMangaData.manga_id == Manga.id) & (UserMangaData.user_id == user_id))
            .where((UserMangaData.is_read == None) | (~UserMangaData.is_read))
            .order_by(SQL.ORDER[sort](Manga.id))
        )
    elif list_name == "history":
        return QUERY_HISTORY(user_id, sort)
    elif list_name == "favorites":
        return QUERY_FAVORITES(user_id, sort)
    else:
        return QUERY_QUEUE(user_id, sort)

def search_query(q: str, sort: Optional[str] = None) -> Select:
    sort = sort if sort in SQL.ORDER else "asc"
    return (
        select(create_search_query(q).subquery().alias("manga"))
        .order_by(SQL.ORDER[sort](Manga.id))
    )

def fetch(query: Select, offset: int, limit: int) -> list[dict]:
    """Runs a (id, title) query for one batch."""
    return db.session.execute_query(query.offset(offset).limit(limit), mappings=["id", "title"])

def count(query: Select) -> int:
    return db.session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))

def random_id(user_id: int, unread_only: bool = False) -> Optional[int]:
    query = select(Manga.id).order_by(func.random())
    if unread_only:
        query = (
            query.outerjoin(UserMangaData, (UserMangaData.manga_id == Manga.id) & (UserMangaData.user_id == user_id))
            .where((UserMangaData.is_read == None) | (~UserMangaData.is_read))
        )
    return db.session.scalar(query.limit(1))

def chapter_page_counts(manga_id: int) -> dict[int, int]:
    """Page count per chapter number, without loading every Page row."""
    rows = db.session.execute(
        select(Page.chapter_number, func.count())
        .where(Page.manga_id == manga_id)
        .group_by(Page.chapter_number)
    ).all()
    return {chapter_number: page_count for chapter_number, page_count in rows}

def reading_state(user_id: int, manga_ids: list[int]) -> dict[int, dict]:
    """Per-manga user state for a batch of list results: chapter count, saved position and pages in that chapter."""
    if not manga_ids:
        return {}

    chapter_counts = dict(db.session.execute(
        select(Chapter.manga_id, func.count())
        .where(Chapter.manga_id.in_(manga_ids))
        .group_by(Chapter.manga_id)
    ).all())

    user_rows = db.session.scalars(
        select(UserMangaData).where(UserMangaData.user_id == user_id, UserMangaData.manga_id.in_(manga_ids))
    ).all()

    current_chapter_pages = dict(db.session.execute(
        select(UserMangaData.manga_id, func.count(Page.number))
        .join(Page, (Page.manga_id == UserMangaData.manga_id) & (Page.chapter_number == UserMangaData.current_chapter))
        .where(UserMangaData.user_id == user_id, UserMangaData.manga_id.in_(manga_ids))
        .group_by(UserMangaData.manga_id)
    ).all())

    states = {manga_id: {"total_chapters": chapter_counts.get(manga_id, 0), "user": None} for manga_id in manga_ids}
    for row in user_rows:
        states[row.manga_id]["user"] = row.toJson()
        states[row.manga_id]["progress"] = progress_fraction(
            row, states[row.manga_id]["total_chapters"], current_chapter_pages.get(row.manga_id, 0)
        )
    return states

def progress_fraction(user_data: UserMangaData, total_chapters: int, pages_in_current_chapter: int) -> float:
    """0 to 1. Unopened manga are 0 and read manga are 1."""
    if user_data.is_read:
        return 1.0
    if user_data.last_seen is None or total_chapters <= 0:
        return 0.0
    within_chapter = user_data.current_page / pages_in_current_chapter if pages_in_current_chapter else 0
    return round(min(1.0, ((user_data.current_chapter - 1) + within_chapter) / total_chapters), 4)

def save_progress(user_id: int, manga: Manga, chapter_number, page_number) -> Optional[UserMangaData]:
    """Saves the reader position. Returns None when the chapter or page doesn't exist.
    Reaching the last page of the last chapter marks the manga read and takes it off the queue."""
    chapter: Chapter = db.Chapter.fromManga(manga, chapter_number)
    if chapter is None:
        return None
    page: Page = db.Page.fromChapter(chapter, page_number)
    if page is None:
        return None

    user_data: UserMangaData = db.UserMangaData.getOrCreate(user_id, manga)
    if user_data.new:
        db.session.add(user_data)

    user_data.current_chapter = chapter.number
    user_data.current_page = page.number
    user_data.last_seen = db.getDatetimeISONow()

    if chapter.number >= len(manga.chapters) and page.number >= len(chapter.pages):
        user_data.is_read = True
        user_data.is_queued = False
        user_data.current_page = 1

    db.session.commit()
    return user_data

def update_state(user_id: int, manga: Manga, is_read: Optional[bool] = None, reset: bool = False,
                 is_favorite: Optional[bool] = None, is_queued: Optional[bool] = None) -> UserMangaData:
    """Changes read, favorite and queue flags. A None flag is left as it is."""
    user_data: UserMangaData = db.UserMangaData.getOrCreate(user_id, manga)
    db.session.begin_nested()
    if user_data.new:
        db.session.add(user_data)

    if is_read is not None:
        user_data.is_read = is_read
    if reset:
        user_data.current_chapter = 1
        user_data.current_page = 1
    if is_favorite is not None:
        user_data.is_favorite = is_favorite
        user_data.favorited_when = db.getDatetimeISONow() if is_favorite else ""
    if is_queued is not None:
        user_data.is_queued = is_queued
        user_data.queued_when = db.getDatetimeISONow() if is_queued else ""

    db.session.commit()
    return user_data
