from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.orm import scoped_session, Session

from datetime import datetime, timezone

from typing import Optional, Final

from .constants import ENV

import os

from sqlalchemy import Select, select, func, exc, inspect, text, event
from sqlalchemy.engine import Engine
import sqlite3

from .models import db_engine, Manga, Chapter, Page, MangaMetadata, UserMangaData, User

from .helpers import release_year_from_names

@event.listens_for(Engine, "connect")
def _add_sql_functions(dbapi_connection, _record):
    # SQLite's lower() and LIKE only ignore case for A-Z; search uses casefold() for every letter
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function(
            "casefold", 1, lambda value: value.casefold() if isinstance(value, str) else value, deterministic=True
        )

class Manga_session(scoped_session):
    session: Session
    def __init__(self, session: Session):
        self.session = session

    def __getattr__(self, name):
        return getattr(self.session, name)

    # This assumes that user is being set somewhere else, may need to change
    def getCurrentUser(self) -> User:
        from flask import g
        return g.user
    
    def getUserID(self) -> int:
        return Manga_session.getCurrentUser(self)["id"]
    
    # Returns the query results as a indexed tuple or a tuple with mappings. e.g. (1,2,3) vs (a=1,b=2,c=3)
    def execute_query(self, query: Select[tuple[int, str]], mappings:list[str]=None):
        if mappings is None:
            return self.session.execute(query).tuples().all()
        else:
            return [{ mappings[i]:result[i] for i in range(len(mappings)) } for result in self.session.execute(query)]

class db:
    session: Manga_session = None

    # Seems like Jinja datetime doesn't preserve the timezone when converting to a string so just skipping the middle man
    def getDatetimeISONow():
        return str(datetime.now(timezone.utc))

    def fromDatetimeISO(iso:str):
        return datetime.fromisoformat(iso)

    class Manga:
        MANGA_COUNT = 0

        def update_manga_count():
            try:
                count = db.session.scalar(
                    select(func.count()).select_from(Manga)
                )
                db.Manga.MANGA_COUNT = count
            except exc.OperationalError:
                db.Manga.MANGA_COUNT = 0 

        def fromID(id: int) -> Optional[Manga]:
            return db.session.scalar(select(Manga).where(Manga.id == id))
            # return Manga.query.get({"id": id})
    
        def fromPath(path: str):
            # TODO Remove?
            return db.session.scalars(select(Manga).where(Manga.path == path)).one_or_none()
    
        def getChapter(number: int) -> Optional[Chapter]:
            return Chapter.fromManga(number)

        def getOrCreate(title:str, manga_path: str) -> Manga:
            manga: Manga = db_engine.session.scalar(select(Manga).where(Manga.path == manga_path))
            if manga is None:
                manga = Manga(title=title, path=manga_path, original_title=title, manga_metadata=MangaMetadata())
                manga.original_title = title
                manga.date_uploaded = str(datetime.now(timezone.utc))
                manga.new = True
                return manga
            else:
                manga.original_title = title
                return manga
            
    class Page:
        def fromChapter(chapter: Chapter, number: int) -> Optional[Page]:
            return db_engine.session.get(Page, {"number": number, "manga_id": chapter.manga_id, "chapter_number": chapter.number})
        
        def create(file_name: str, number: int):
            page = Page(number=number, file_name=file_name)
            return page
        
    class Chapter:
        def fromManga(manga: Manga, number: int) -> Optional[Chapter]:
            return db_engine.session.get(Chapter, {"manga_id": manga.id, "number": number})
        
        def create(chapter_path: str, number: int, title: str, archive_type: str = None) -> Chapter:
            chapter = Chapter(number=number, path=chapter_path, archive_type=archive_type)
            chapter.title = title
            return chapter

    class UserMangaData:
        def getOrCreate(userID: int, manga: "Manga"):
            user_data = db.UserMangaData.fromUserAndManga(userID, manga)
            if user_data is None:
                user_data = UserMangaData(user_id=userID, manga_id=manga.id)
                user_data.new = True

            return user_data
    
        def fromUserAndManga(userID: int, manga: "Manga"):
            return db_engine.session.get(UserMangaData, {"user_id": userID, "manga_id": manga.id })

def init_app(app: Flask):
    if app.config.get("SQLALCHEMY_DATABASE_URI", None) is None:
        if app.config.get('DATABASE_PATH', None) is None:
            app.config['DATABASE_PATH'] = f"{app.instance_path}/{ENV.DEFAULT_DATABASE}"
        print(f"Loaded Database at {app.config['DATABASE_PATH']}")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{app.config['DATABASE_PATH']}"

    db_engine.init_app(app)
        
    if not os.path.exists(app.config['DATABASE_PATH']):
        print(f"Database not found: {app.config['DATABASE_PATH']}")
        print("Creating the database...")
        with app.app_context():
            db_engine.create_all()
        if not os.path.exists(app.config['DATABASE_PATH']):
            print("Unable to make database")
            exit()
    else:
        # Adds tables and columns introduced by newer versions (e.g. api_token, manga.release_year)
        with app.app_context():
            db_engine.create_all()
            add_missing_columns()
            add_missing_indexes()
            fill_missing_release_years()
            normalize_languages()
            from .server.metadata import fill_missing_from_files
            fill_missing_from_files()

def add_missing_columns():
    """create_all() only makes missing tables. This adds new nullable columns to tables that already exist."""
    inspector = inspect(db_engine.engine)
    with db_engine.engine.begin() as connection:
        for table in db_engine.metadata.sorted_tables:
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable and not column.primary_key:
                    column_type = column.type.compile(dialect=db_engine.engine.dialect)
                    print(f"Adding column {table.name}.{column.name}")
                    connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))

def add_missing_indexes():
    """create_all() skips tables that already exist, indexes included. This adds the indexes the models
    declare to an existing database. It changes no data, and older versions simply ignore them."""
    inspector = inspect(db_engine.engine)
    with db_engine.engine.begin() as connection:
        for table in db_engine.metadata.sorted_tables:
            existing = {index["name"] for index in inspector.get_indexes(table.name)}
            for index in table.indexes:
                if index.name not in existing:
                    print(f"Adding index {index.name}")
                    index.create(bind=connection, checkfirst=True)

def fill_missing_release_years():
    """Works out release years for manga scanned before they were tracked, from the names already stored."""
    rows = db_engine.session.execute(
        select(Manga.id, Manga.title, Manga.path, Chapter.title)
        .outerjoin(Chapter, Chapter.manga_id == Manga.id)
        .where(Manga.release_year.is_(None))
    ).all()
    names: dict[int, list[str]] = {}
    for manga_id, title, path, chapter_title in rows:
        names.setdefault(manga_id, [title, os.path.basename(path or "")]).append(chapter_title)

    updated = 0
    for manga_id, manga_names in names.items():
        year = release_year_from_names(manga_names)
        if year is not None:
            db_engine.session.get(Manga, manga_id).release_year = year
            updated += 1
    if updated:
        db_engine.session.commit()
        print(f"Found release years for {updated} manga")

def normalize_languages():
    """Turns languages stored as free text ("English", "en-US", "jp") into the fixed codes search uses.
    Values that can't be matched are left as they are."""
    from .server.languages import normalize
    updated = 0
    for meta in db_engine.session.scalars(select(MangaMetadata).where(MangaMetadata.language.is_not(None), MangaMetadata.language != "")):
        code = normalize(meta.language)
        if code != meta.language:
            meta.language = code
            updated += 1
    if updated:
        db_engine.session.commit()
        print(f"Updated the language of {updated} manga")

db.session = Manga_session(db_engine.session)