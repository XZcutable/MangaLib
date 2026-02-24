from typing import Optional, List
from typing_extensions import Annotated

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import ForeignKey, ForeignKeyConstraint, select
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Mapped, mapped_column, relationship

from datetime import datetime, timezone

from .enum import Access
from .constants import ENV

import os, re, zipfile, fitz, pymupdf

# TODO Issue importing these from Manga, maybe import from here instead?
image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')
archive_types = ('.cbz', '.zip', '.pdf')

class BaseModel(DeclarativeBase, MappedAsDataclass):
    def __getitem__(self, key):
        return getattr(self, key)
    pass

db = SQLAlchemy(model_class=BaseModel)
Base = db.Model

int_pk = Annotated[int, mapped_column(primary_key=True)]
str_pk = Annotated[str, mapped_column(primary_key=True)]
unique_str = Annotated[str, mapped_column(unique=True)]
manga_id_fk = Annotated[int, mapped_column(ForeignKey("manga.id"))]

def init_app(app: Flask):
    database_path: str = app.config.get('DATABASE_PATH', ENV.DEFAULT_DATABASE_PATH)
    database_name: str = app.config.get('DATABASE_NAME', ENV.DEFAULT_DATABASE_NAME)
    if app.config.get("SQLALCHEMY_DATABASE_URI", None) is None:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}/{database_name}"
        app.config["SQLALCHEMY_ECHO"] = False
    db.init_app(app)
        
    cur_dir = os.getcwd()
    os.chdir(app.instance_path)
    if not os.path.exists(f"{database_path}/{database_name}"):
        print(f"Database not found: {database_path}/{database_name}")
        print("Creating the database...")
        os.chdir(cur_dir)
        with app.app_context():
            db.create_all()
        os.chdir(app.instance_path)
        if not os.path.exists(f"{database_path}/{database_name}"):
            print("Unable to make database")
            exit()
    os.chdir(cur_dir)

class Path(db.Model):
    path: Mapped[str_pk]

    def sortList(path_list: list[str], isDirs=False):
        if isDirs:
            path_list.sort(key=lambda path: Path.alphanum_key(str.casefold(path)))
        else:
            path_list.sort(key=lambda path: Path.alphanum_key(os.path.splitext(str.casefold(path))[0]))

    alphanum_key = lambda key: [c for c in re.split('([0-9]+)', str.casefold(key))]

# Username, passwords, preferences
class User(Base):
    __tablename__ = "user"
    id:Mapped[int_pk] = mapped_column(unique=True, init=False)
    username: Mapped[unique_str]
    password: Mapped[str]

    approved: Mapped[bool] = mapped_column(default=False)
    role: Mapped[str] = mapped_column(default=Access.USER.toString())
    date_created: Mapped[str] = mapped_column(default=None)
    email: Mapped[Optional[str]] = mapped_column(default=None)

    def __repr__(self):
        return f'<Name {self.username}>  ID {self.id} ({self.email}) Created "{self.date_created}" <approved: {self.approved}>'
    
    def create(username: str, password_hash: str) -> "User":
        user = User(username=username, password=password_hash, date_created=str(datetime.now(timezone.utc)))
        return user
    
class UserMangaData(Base):
    user_id:Mapped[int_pk] = mapped_column(ForeignKey("user.id"))
    manga_id:Mapped[manga_id_fk] = mapped_column(primary_key=True)

    current_chapter:Mapped[int] = mapped_column(default=1)
    current_page:Mapped[int] = mapped_column(default=1)
    is_read:Mapped[bool] = mapped_column(default=False)
    is_favorite:Mapped[bool] = mapped_column(default=False)
    is_queued:Mapped[bool] = mapped_column(default=False)
    favorited_when:Mapped[Optional[str]] = mapped_column(default=None)
    queued_when:Mapped[Optional[str]] = mapped_column(default=None)
    last_seen:Mapped[Optional[str]] = mapped_column(default=None)

    manga:Mapped["Manga"] = relationship(default=None, viewonly=True)

    new:bool = False

    def toJson(self):
        return {
            "user_id": self.user_id,
            "manga_id": self.manga_id,
            "current_chapter": self.current_chapter,
            "current_page": self.current_page,
            "is_read": self.is_read,
            "is_favorite": self.is_favorite,
            "is_queued": self.is_queued,
            "favorited_when": self.favorited_when,
            "queued_when": self.queued_when,
            "last_seen": self.last_seen,
        }

    def getOrCreate(userID: int, manga: "Manga"):
        user_data = UserMangaData.fromUserAndManga(userID, manga)
        if user_data is None:
            user_data = UserMangaData(user_id=userID, manga_id=manga.id)
            user_data.new = True

        return user_data
    
    def fromUserAndManga(userID: int, manga: "Manga"):
        return UserMangaData.query.get({"user_id": userID, "manga_id": manga.id })
    
    def __repr__(self):
        return f"<UserMangaData({self.user_id=}, {self.manga_id=}, {self.current_chapter=}, {self.current_page=}, {self.is_read=}, {self.is_favorite=}, {self.last_seen=})>"


class ContentTag(Base):
    __tablename__ = "content_tag"
    tag:Mapped[str_pk] = mapped_column(unique=True)
    nsfw:Mapped[bool] = mapped_column(default=False)
    mangas:Mapped[List["MangaMetadata"]] = relationship(default_factory=list, secondary="manga_content_tag", back_populates="tags")

    def __repr__(self):
        return f"<Tag({self.tag=}, {self.nsfw=})>"
    
    def toJson(self):
        return {
            "tag": self.tag,
            "nsfw": self.nsfw,
        }

class MangaContentTag(Base):
    __tablename__ = "manga_content_tag"
    manga_id:Mapped[int_pk] = mapped_column(ForeignKey("manga_metadata.manga_id"))
    tag:Mapped[str_pk] = mapped_column(ForeignKey("content_tag.tag"))

class MangaMetadata(Base):
    __tablename__ = "manga_metadata"
    manga_id:Mapped[manga_id_fk] = mapped_column(init=False, primary_key=True)

    tags:Mapped[List["ContentTag"]] = relationship(default_factory=list, secondary="manga_content_tag", back_populates="mangas")
    language:Mapped[Optional[str]] = mapped_column(default="")

    def toJson(self):
        return {
            "manga_id": self.manga_id,
            "language": self.language,
            "tags": [tag.toJson() for tag in self.tags],
        }

    def __repr__(self):
        return f"<Metadata({self.manga_id=}, {self.language=}, {self.tags=})>"

class Manga(Base):
    __tablename__ = "manga"
    id:Mapped[int_pk] = mapped_column(init=False, unique=True)
    title:Mapped[str]
    original_title:Mapped[str]
    path: Mapped[str]

    manga_metadata:Mapped["MangaMetadata"] = relationship(cascade="all, delete-orphan")

    chapters:Mapped[List["Chapter"]] = relationship(default_factory=list, back_populates="manga", cascade="all, delete-orphan")

    date_uploaded:Mapped[str] = mapped_column(default=None)
    relative_path:Mapped[str] = mapped_column(default="")

    new = False

    def getChapter(self, number: int) -> Optional["Chapter"]:
        return Chapter.fromManga(self, number)

    def getOrCreate(title:str, manga_path: str) -> "Manga":
        manga: Manga = db.session.scalar(select(Manga).where(Manga.path == manga_path))
        if manga is None:
            manga = Manga(title=title, path=manga_path, original_title=title, manga_metadata=MangaMetadata())
            manga.original_title = title
            manga.date_uploaded = str(datetime.now(timezone.utc))
            manga.new = True
            return manga
        else:
            manga.original_title = title
            return manga  

    def __repr__(self):
        return f"<Manga({self.id=}, {self.title=}, {self.chapters=}, {self.manga_metadata=})>"
    
    def toJson(self):
        return {
            "id": self.id,
            "title": self.title,
            "original_title": self.original_title,
            "total_chapters": len(self.chapters),
            "manga_metadata": self.manga_metadata.toJson(),
            "date_uploaded": self.date_uploaded,
        }

    def fromID(id: int) -> Optional["Manga"]:
        return Manga.query.get({"id": id})
    
    def fromPath(path: str):
        return Manga.query.filter_by(path=path).one_or_none()

class Chapter(Base):
    __tablename__ = "chapter"
    manga_id:Mapped[manga_id_fk] = mapped_column(init=False, primary_key=True)
    number:Mapped[int_pk]
    path: Mapped[str]
    archive_type: Mapped[Optional[str]] = mapped_column(default=None, nullable=True)

    title:Mapped[Optional[str]] = mapped_column(default="")
    manga:Mapped["Manga"] = relationship(default=None, back_populates="chapters")

    pages:Mapped[List["Page"]] = relationship(default_factory=list, cascade="all, delete-orphan", back_populates="chapter")

    def is_archive(self):
        return self.archive_type is not None 

    def getPage(self, number: int) -> Optional["Page"]:
        return Page.fromChapter(self, number)

    def __repr__(self):
        return f"<Chapter({self.manga_id=}, {self.title=}, {self.number=}, {self.pages=})"
    
    def toJson(self):
        return {
            'manga_id': self.manga_id,
            'title': self.title,
            'number': self.number,
            'page_count': len(self.pages),
        }
   
    def fromManga(manga: Manga, number: int) -> Optional["Chapter"]:
         return db.session.get(Chapter, {"manga_id": manga.id, "number": number})
    
    def create(chapter_path: str, number: int, title: str, archive_type: str = None) -> "Chapter":
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
                        if entry_ext in image_types:
                            files.append(entry.filename)
                
                Path.sortList(files)
                next_page_number = 1
                for file in files:
                    page: Page = Page.create(file_name=file, number=next_page_number)
                    next_page_number += 1
                    chapter.pages.append(page)
        elif archive_ext == '.pdf':
            pdf = pymupdf.open(archive_path)
            for page_index in range(len(pdf)):
                page = pdf.load_page(page_index)
                image_list = [xref[0] for xref in page.get_images(full=True)]

                for xref in image_list:
                    files.append(xref)

            files.sort()
            next_page_number = 1
            for xref in files:
                page: Page = Page.create(file_name=f"{xref}", number=next_page_number)
                next_page_number += 1
                chapter.pages.append(page)
        else:
            print(f"{archive_ext} is not yet supported.")

        return len(files)
    
class Page(Base):
    __tablename__ = "page"
    number:Mapped[int_pk]
    manga_id:Mapped[int_pk] = mapped_column(init=False)
    chapter_number:Mapped[int_pk] = mapped_column(init=False)
    file_name: Mapped[str]

    manga:Mapped["Manga"] = relationship("Manga", foreign_keys=[manga_id], default=None, viewonly=True)
    chapter:Mapped["Chapter"] = relationship(foreign_keys=[manga_id, chapter_number], default=None, viewonly=True)

    __table_args__ = (
        ForeignKeyConstraint(
            [manga_id], ["manga.id"]
        ),
        ForeignKeyConstraint(
            [manga_id, chapter_number], ["chapter.manga_id", "chapter.number"]
        ),
    )

    def __repr__(self):
        return f"<Page({self.number=}, {self.file_name=}, {self.manga_id=}, {self.chapter_number=})>"
    
    def toJson(self):
        return {
            "number": self.number,
            "file_name": self.file_name,
            "manga_id": self.manga_id,
            "chapter_number": self.chapter_number,

            "manga": self.manga.id,
            "chapter": self.chapter.number,
        }
    
    def fromChapter(chapter: Chapter, number: int) -> Optional["Page"]:
        return db.session.get(Page, {"number": number, "manga_id": chapter.manga_id, "chapter_number": chapter.number})
    
    def create(file_name: str, number: int):
        page = Page(number=number, file_name=file_name)
        return page

class Metadata():
    pass