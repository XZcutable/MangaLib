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
manga_id_fk = Annotated[int, mapped_column(ForeignKey("manga.id"), primary_key=True)]

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
class Users(Base):
    id:Mapped[int_pk] = mapped_column(unique=True)
    username: Mapped[unique_str]
    password: Mapped[str]

    email: Mapped[Optional[str]]
    approved: Mapped[bool] = mapped_column(default=False)
    role: Mapped[str] = mapped_column(default=Access.USER.toString())
    date_created: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Name {self.username}>  ID {self.id} ({self.email}) Created "{self.date_created}" <approved: {self.approved}>'

class Manga(Base):
    __tablename__ = "manga"
    id:Mapped[int_pk] = mapped_column(init=False, unique=True)
    title:Mapped[str]
    path: Mapped[str]

    chapters:Mapped[List["Chapter"]] = relationship(default_factory=list, cascade="all, delete-orphan", back_populates="manga")

    date_uploaded:Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))

    new = False

    def getChapter(self, number: int) -> Optional["Chapter"]:
        return Chapter.fromManga(self, number)

    def getOrUpdate(title, manga_path) -> "Manga":
        manga = Manga.query.filter_by(path=manga_path).one_or_none()
        if manga is None:
            manga = Manga(title=title, path=manga_path)
            manga.new = True
            return manga
        else:
            manga.new = False
            manga.title = title
            manga.path = manga_path
            return manga  

    def __repr__(self):
        return f"<Manga(id={self.id}, title={self.title}, chapters={self.chapters})>"
    
    def fromID(id: int) -> Optional["Manga"]:
        return Manga.query.get({"id": id})
    
    def fromPath(path: str):
        return Manga.query.filter_by(path=path).one_or_none()

class Chapter(Base):
    __tablename__ = "chapter"
    manga_id:Mapped[manga_id_fk] = mapped_column(init=False)
    number:Mapped[int_pk]
    path: Mapped[str]

    title:Mapped[str] = mapped_column(default="")
    manga:Mapped["Manga"] = relationship(default=None, back_populates="chapters")

    pages:Mapped[List["Page"]] = relationship(default_factory=list, cascade="all, delete-orphan", back_populates="chapter")

    new = False

    def getPage(self, number: int) -> Optional["Page"]:
        return Page.fromChapter(self, number)

    def __repr__(self):
        return f"<Chapter(manga_id={self.manga_id}, title={self.title}, number={self.number}, {self.pages=})"
   
    def fromManga(manga: Manga, number: int) -> Optional["Chapter"]:
         return Chapter.query.get({"manga_id": manga.id, "number": number})
    
    def sortList(page_list: list["Chapter"]):
        page_list.sort(key=lambda chapter: chapter.number)
    
    def getOrUpdate(manga: Manga, chapter_path: str, number: int) -> "Chapter":
        chapter = Chapter.fromManga(manga, number)
        if chapter is None:
            chapter = Chapter(number=number, path=chapter_path)
            chapter.new = True
            return chapter
        else:
            chapter.path = chapter_path
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
        return f"<Page({self.number=}, {self.file_name=}, {self.manga_id=}, {self.chapter_number=})>"
    
    def fromChapter(chapter: Chapter, number: int) -> Optional["Page"]:
        return Page.query.get({"number": number, "manga_id": chapter.manga_id, "chapter_number": chapter.number})
    
    def getOrUpdate(chapter: Chapter, file_name: str, number: int):
        page = Page.fromChapter(chapter, number)
        if page is None:
            page = Page(file_name=file_name, number=number)
            page.new = True
            return page
        else:
            page.new = False
            page.file_name = file_name
            return page

class Metadata():
    pass