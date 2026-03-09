from typing import Final
from sqlalchemy import select
from sqlalchemy.sql.selectable import Select

from .database import db
from .models import Manga, Chapter, Path, UserMangaData
from sqlalchemy import and_, select
from .constants import ENDPOINT, SQL

GET_PATHS: Final[Select] = select(Path)

def query(stmt: Select):
    return db.session.scalars(stmt)

def QUERY_HISTORY(user_id: int, sort: str = SQL.ASC) -> Select:
    return (
        select(Manga.id, Manga.title)
        .join(UserMangaData, 
            onclause=and_(
                UserMangaData.user_id == user_id,
                Manga.id == UserMangaData.manga_id
            )
        ).order_by(SQL.ORDER.get(sort, SQL.ASC)(UserMangaData.last_seen).nulls_last())
    )

def QUERY_FAVORITES(user_id: int, sort: str = SQL.ASC) -> Select:
    return (
        select(Manga.id, Manga.title)
        .join(UserMangaData, 
            onclause=and_(
                UserMangaData.user_id == user_id,
                UserMangaData.is_favorite,
                Manga.id == UserMangaData.manga_id
            )
        ).order_by(SQL.ORDER.get(sort, SQL.ASC)(UserMangaData.favorited_when).nulls_last())
    )

def QUERY_QUEUE(user_id: int, sort: str = SQL.ASC) -> Select:
    return (
        select(Manga.id, Manga.title)
        .join(UserMangaData, 
            onclause=and_(
                UserMangaData.user_id == user_id,
                UserMangaData.is_queued,
                Manga.id == UserMangaData.manga_id
            )
        ).order_by(SQL.ORDER.get(sort, SQL.ASC)(UserMangaData.queued_when).nulls_last())
    )


QUERY_PATHS: Final[Select] = select(
    Path.path
)