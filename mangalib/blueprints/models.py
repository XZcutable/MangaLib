from typing import Optional, List
from typing_extensions import Annotated

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import click

from sqlalchemy import ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Mapped, mapped_column, relationship

from datetime import datetime, timezone

from mangalib.lib.enum import Access

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

    def sortList(page_list: list[str]):
        page_list.sort(key=str.casefold)
        page_list.sort(key=len)

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
        return f"<UserMangaData({self.user_id=}, {self.manga_id=}, {self.current_chapter=}, {self.current_page=}, {self.is_read=}, {self.is_favorite=})>"


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


    manga_metadata:Mapped["MangaMetadata"] = relationship()

    chapters:Mapped[List["Chapter"]] = relationship(default_factory=list, back_populates="manga")

    date_uploaded:Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))

    new = False

    def getChapter(self, number: int) -> Optional["Chapter"]:
        return Chapter.fromManga(self, number)

    def getOrCreate(title:str, manga_path: str) -> "Manga":
        manga: Manga = Manga.query.filter_by(path=manga_path).one_or_none()
        if manga is None:
            manga = Manga(title=title, path=manga_path)
            manga.manga_metadata = MangaMetadata()
            manga.original_title = title
            manga.new = True
            return manga
        else:
            manga.original_title = title
            if manga.manga_metadata is None:
                manga.manga_metadata = MangaMetadata()
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
    
    def sortList(page_list: list["Chapter"]):
        page_list.sort(key=lambda chapter: chapter.number)
    
    def getOrCreate(manga: Manga, chapter_path: str, number: int) -> "Chapter":
        # chapter = Chapter.fromManga(manga, number)
        chapter = Chapter.query.filter_by(manga_id=manga.id, path=chapter_path).one_or_none()
        if chapter is None:
            chapter = Chapter(number=number, path=chapter_path)
            chapter.new = True
            return chapter
        else:
            chapter.new = False
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

    def sortList(page_list: list["Page"]):
        page_list.sort(key=lambda page: str.casefold(page.file_name))
        page_list.sort(key=lambda page: len(page.file_name))

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
    
    def getOrCreate(chapter: Chapter, file_name: str, next_number: int):
        page = Page.query.filter_by(manga_id=chapter.manga_id, chapter_number=chapter.number, file_name=file_name).one_or_none()
        if page is None:
            page = Page(number=next_number, file_name=file_name)
            page.new = True
            return page
        else:
            return page

class Metadata():
    pass