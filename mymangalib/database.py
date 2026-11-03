from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.orm import scoped_session, Session

from datetime import datetime, timezone

from typing import Optional, Final

from .constants import ENV

import os, zipfile, pymupdf

from sqlalchemy import Select, select, func, exc, inspect, text

from .models import db_engine, Manga, Chapter, Page, MangaMetadata, UserMangaData, User

from .helpers import sort_paths, release_year_from_names

SUPPORTED_IMAGE_TYPES: Final[tuple] = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')
SUPPORTED_ARCHIVE_TYPES: Final[tuple] = ('.cbz', '.zip', '.pdf')

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
        
        def from_archive(chapter: "Chapter", archive_path: str, archive_ext: str):
            files = []
            if archive_ext == '.cbz' or archive_ext == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_file:
                    # iterates through all files and folders. treating all as one chapter but is more of a volume
                    for entry in zip_file.infolist():
                        if entry.is_dir():
                            pass
                        else:
                            entry_ext = os.path.splitext(entry.filename)[1]
                            if entry_ext in SUPPORTED_IMAGE_TYPES:
                                files.append(entry.filename)
                    
                    sort_paths(files)
                    next_page_number = 1
                    for file in files:
                        page: Page = db.Page.create(file_name=file, number=next_page_number)
                        next_page_number += 1
                        chapter.pages.append(page)
            elif archive_ext == '.pdf':
                pdf = pymupdf.open(archive_path)
                for page_index in range(len(pdf)):
                    page = pdf.load_page(page_index)
                    image_list = [xref[0] for xref in page.get_images(full=True)]

                    for xref in image_list:
                        files.append(xref)

                next_page_number = 1
                for xref in files:
                    page: Page = db.Page.create(file_name=f"{xref}", number=next_page_number)
                    next_page_number += 1
                    chapter.pages.append(page)
            else:
                print(f"{archive_ext} is not yet supported.")

            return len(files)

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
            fill_missing_release_years()

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

db.session = Manga_session(db_engine.session)