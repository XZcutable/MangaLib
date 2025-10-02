from typing import Optional, List
from typing_extensions import Annotated

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import click

from sqlalchemy import ForeignKey, ForeignKeyConstraint, select
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Mapped, mapped_column, relationship

from datetime import datetime, timezone

from app.enum import Access

import os

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
    if app.config.get("SQLALCHEMY_DATABASE_URI", None) is None:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{app.config.get('DATABASE_PATH', '')}/database.db"
        app.config["SQLALCHEMY_ECHO"] = False

    db.init_app(app)
    app.cli.add_command(init_db)

@click.command('init-db')
def init_db():
    click.echo('Initializing database')
    db.create_all()

class Path(db.Model):
    path: Mapped[str_pk]

    def sortList(path_list: list[str]):
        path_list.sort(key=lambda path: str.casefold(os.path.splitext(path)[0]))
        path_list.sort(key=lambda path: len(os.path.splitext(path)[0]))

# Username, passwords, preferences
class User(Base):
    __tablename__ = "user"
    id:Mapped[int_pk] = mapped_column(unique=True)
    username: Mapped[unique_str]
    password: Mapped[str]

    email: Mapped[Optional[str]]
    approved: Mapped[bool] = mapped_column(default=False)
    role: Mapped[str] = mapped_column(default=Access.USER.toString())
    date_created: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Name {self.username}>  ID {self.id} ({self.email}) Created "{self.date_created}" <approved: {self.approved}>'
    
class UserMangaData(Base):
    user_id:Mapped[int_pk] = mapped_column(ForeignKey("user.id"))
    manga_id:Mapped[manga_id_fk] = mapped_column(primary_key=True)

    current_chapter:Mapped[int] = mapped_column(default=1)
    current_page:Mapped[int] = mapped_column(default=1)
    is_read:Mapped[bool] = mapped_column(default=False)
    is_favorite:Mapped[bool] = mapped_column(default=False)
    favorited_when:Mapped[Optional[datetime]] = mapped_column(default=None, nullable=True)
    last_seen:Mapped[Optional[datetime]] = mapped_column(default=None, nullable=True)

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
            "favorited_when": self.favorited_when,
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

    date_uploaded:Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))

    new = False

    def getChapter(self, number: int) -> Optional["Chapter"]:
        return Chapter.fromManga(self, number)

    def getOrCreate(title:str, manga_path: str) -> "Manga":
        manga: Manga = Manga.query.filter_by(path=manga_path).one_or_none()
        if manga is None:
            manga = Manga(title=title, path=manga_path, original_title=title, manga_metadata=MangaMetadata())
            manga.original_title = title
            manga.new = True
            return manga
        else:
            manga.original_title = title
            # if manga.manga_metadata is None:
            #     manga.manga_metadata = MangaMetadata()
            return manga  

    def __repr__(self):
        # return json.dumps(self.toJson())
        return f"<Manga({self.id=}, {self.title=}, {self.chapters=}, {self.manga_metadata=})>"
    
    def toJson(self, shallow_copy=False):
        if shallow_copy:
            return {
                "id": self.id,
                "title": self.title,
                "chapters": [chapter.toJson(True) for chapter in self.chapters],
                "manga_metadata": self.manga_metadata.toJson(),
                # TODO Add this to the model so i don't have to do this
                "original_title": self.original_title,
            }
        else:
            return {
                "id": self.id,
                "title": self.title,
                "original_title": self.original_title,
                "chapters": [chapter.toJson() for chapter in self.chapters],
                "manga_metadata": self.manga_metadata.toJson(),
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

    title:Mapped[Optional[str]] = mapped_column(default="")
    manga:Mapped["Manga"] = relationship(default=None, back_populates="chapters")

    pages:Mapped[List["Page"]] = relationship(default_factory=list, cascade="all, delete-orphan", back_populates="chapter")

    new = False

    def getPage(self, number: int) -> Optional["Page"]:
        return Page.fromChapter(self, number)

    def __repr__(self):
        # return json.dumps(self.toJson())
        return f"<Chapter({self.manga_id=}, {self.title=}, {self.number=}, {self.pages=})"
    
    def toJson(self, shallow_copy=False):
        if shallow_copy:
            return {
                'manga_id': self.manga_id,
                'title': self.title,
                'number': self.number,
                "pages": [page.toJson(True) for page in self.pages],
            }
        else:
            return {
                'manga_id': self.manga_id,
                'title': self.title,
                'number': self.number,
                "pages": [page.toJson() for page in self.pages],

                "manga": self.manga.toJson(True),
            }
   
    def fromManga(manga: Manga, number: int) -> Optional["Chapter"]:
         return Chapter.query.get({"manga_id": manga.id, "number": number})
    
    def sortList(chapter_list: list["Chapter"]):
        if len(chapter_list) <= 1:
            return
        print([(chapter.number, chapter.title) for chapter in chapter_list])
        chapter_list.sort(key=lambda chapter: str.casefold(chapter.title))

        db.session.begin_nested()
        for i in range(len(chapter_list)):
            chapter_list[i].number = -chapter_list[i].number
            for page in chapter_list[i].pages:
                page.chapter_number = -page.chapter_number
        db.session.commit()
        db.session.begin_nested()
        for i in range(len(chapter_list)):
            chapter_list[i].number = i + 1
            for page in chapter_list[i].pages:
                page.chapter_number = i + 1
        db.session.commit()

        print("sorted")
        print([(chapter.number, chapter.title) for chapter in chapter_list])
    
    def getOrCreate(manga: Manga, chapter_path: str, number: int, title: str) -> "Chapter":
        chapter_query = (
            select(Chapter).where(Chapter.manga_id == Manga.id).where(Chapter.path == chapter_path)
        )
        chapter: Chapter = db.session.scalar(chapter_query)
        if chapter is None:
            chapter = Chapter(number=number, path=chapter_path)
            chapter.new = True
            chapter.title = title
            return chapter
        else:
            chapter.new = False
            chapter.title = title
            return chapter
    
class Page(Base):
    __tablename__ = "page"
    number:Mapped[int_pk]
    manga_id:Mapped[int_pk] = mapped_column(init=False)
    chapter_number:Mapped[int_pk] = mapped_column(init=False)
    file_name: Mapped[str]

    manga:Mapped["Manga"] = relationship("Manga", foreign_keys=[manga_id], default=None, viewonly=True)
    chapter:Mapped["Chapter"] = relationship(foreign_keys=[manga_id, chapter_number], default=None, viewonly=True)

    new = False

    def addPagesAndSort(chapter: Chapter, file_list: list[str]):
        Path.sortList(file_list)

        file_count = len(file_list)
        page_count = len(chapter.pages)
        if file_count < page_count:
            # print("Files Missing")
            for index in range(page_count - 1, file_count - 1, -1):
                page = chapter.pages[index]
                db.session.delete(page)
                chapter.pages.pop(index)

        for i in range(file_count):
            page_number = i + 1
            page: Page = Page.getOrCreate(chapter, file_name=file_list[i], number=page_number)
            if page.new:
                chapter.pages.append(page)

    def sortList(page_list: list["Page"]):
        file_list = [page.file_name for page in page_list]
        
        Path.sortList(file_list)

        for page in page_list:
            page.file_name = file_list[page.number - 1]


    __table_args__ = (
        ForeignKeyConstraint(
            [manga_id], ["manga.id"]
        ),
        ForeignKeyConstraint(
            [manga_id, chapter_number], ["chapter.manga_id", "chapter.number"]
        ),
    )

    def __repr__(self):
        # return json.dumps(self.toJson())
        return f"<Page({self.number=}, {self.file_name=}, {self.manga_id=}, {self.chapter_number=})>"
    
    def toJson(self, shallow_copy=False):
        if shallow_copy:
                return {
                "number": self.number,
                "file_name": self.file_name,
                "manga_id": self.manga_id,
                "chapter_number": self.chapter_number,
            }
        else:
            return {
                "number": self.number,
                "file_name": self.file_name,
                "manga_id": self.manga_id,
                "chapter_number": self.chapter_number,

                "manga": self.manga.toJson(True),
                "chapter": self.chapter.toJson(True),
            }
    
    def fromChapter(chapter: Chapter, number: int) -> Optional["Page"]:
        return Page.query.get({"number": number, "manga_id": chapter.manga_id, "chapter_number": chapter.number})
    
    def getOrCreate(chapter: Chapter, file_name: str, number: int):
        page: Page = Page.query.filter_by(manga_id=chapter.manga_id, chapter_number=chapter.number, number=number).one_or_none()
        # page_query = (
        #     select(Page).where(Page.manga_id == chapter.manga_id).where(Page.chapter_number == chapter.number)
        # )
        # page: Page = db.session.scalar(page_query)
        if page is None:
            page = Page(number=number, file_name=file_name)
            page.new = True
            return page
        else:
            if page.file_name != file_name:
                page.file_name = file_name
            return page

class Metadata():
    pass