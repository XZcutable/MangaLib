from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.orm import scoped_session, Session

from datetime import datetime, timezone

from typing import Optional

from .constants import ENV

import os, zipfile, pymupdf

from sqlalchemy import select, func, exc

from .models import db_engine, Manga, Chapter, Page, MangaMetadata, UserMangaData

from .helpers import sort_paths

from .server.settings import SUPPORTED_IMAGE_TYPES, SUPPORTED_ARCHIVE_TYPES

class db:
    session: scoped_session[Session] = None

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
            return Manga.query.get({"id": id})
    
        def fromPath(path: str):
            return Manga.query.filter_by(path=path).one_or_none()
    
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
                    page: Page = Page.create(file_name=f"{xref}", number=next_page_number)
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
            return UserMangaData.query.get({"user_id": userID, "manga_id": manga.id })

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

db.session = db_engine.session