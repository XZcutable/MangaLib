from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, mapped_column, Mapped, mapped_column, relationship

from datetime import datetime, timezone

from typing import Optional, Annotated, List

import os, re
from .enum import Access

int_pk = Annotated[int, mapped_column(primary_key=True)]
str_pk = Annotated[str, mapped_column(primary_key=True)]
unique_str = Annotated[str, mapped_column(unique=True)]
manga_id_fk = Annotated[int, mapped_column(ForeignKey("manga.id"))]

class BaseModel(DeclarativeBase):
    def __getitem__(self, key):
        return getattr(self, key)

db_engine = SQLAlchemy(model_class=BaseModel)

# Dataclass behaviour is added here rather than on BaseModel. Flask-SQLAlchemy copies
# BaseModel into a new class, and SQLAlchemy 2.1+ rejects copying a class that is already a dataclass.
class Model(MappedAsDataclass, db_engine.Model):
    __abstract__ = True

class Path(Model):
    path: Mapped[str_pk]

    def sortList(path_list: list[str], isDirs=False):
        if isDirs:
            path_list.sort(key=lambda path: Path.alphanum_key(str.casefold(path)))
        else:
            path_list.sort(key=lambda path: Path.alphanum_key(os.path.splitext(str.casefold(path))[0]))

    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [Path.convert(c) for c in re.split('([0-9]+)', str.casefold(key))]

# Username, passwords, preferences
class User(Model):
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

    def toJson(self):
        role = Access.fromString(self.role)
        return {
            "id": self.id,
            "username": self.username,
            "role": str(role),
            "approved": self.approved,
            "is_owner": role == Access.OWNER,
            "is_admin": role >= Access.ADMIN,
            "is_mod": role >= Access.MODERATOR,
        }

# Login tokens for apps that can't use the browser cookie (mobile app, separate web client).
# Only a hash is stored, so a leaked database can't be used to log in.
class ApiToken(Model):
    __tablename__ = "api_token"
    id: Mapped[int_pk] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(default="")
    created: Mapped[Optional[str]] = mapped_column(default=None)
    last_used: Mapped[Optional[str]] = mapped_column(default=None)

    def toJson(self):
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "last_used": self.last_used,
        }

class UserMangaData(Model):
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
 
    def __repr__(self):
        return f"<UserMangaData({self.user_id=}, {self.manga_id=}, {self.current_chapter=}, {self.current_page=}, {self.is_read=}, {self.is_favorite=}, {self.last_seen=})>"


class ContentTag(Model):
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

class MangaContentTag(Model):
    __tablename__ = "manga_content_tag"
    manga_id:Mapped[int_pk] = mapped_column(ForeignKey("manga_metadata.manga_id"))
    tag:Mapped[str_pk] = mapped_column(ForeignKey("content_tag.tag"))

class MangaMetadata(Model):
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

class Manga(Model):
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
    
    def toJson(self):
        return {
            "id": self.id,
            "title": self.title,
            "original_title": self.original_title,
            "total_chapters": len(self.chapters),
            "manga_metadata": self.manga_metadata.toJson(),
            "date_uploaded": self.date_uploaded,
        }

class Chapter(Model):
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

    def __repr__(self):
        return f"<Chapter({self.manga_id=}, {self.title=}, {self.number=}, {self.pages=})"
    
    def toJson(self):
        return {
            'manga_id': self.manga_id,
            'title': self.title,
            'number': self.number,
            'page_count': len(self.pages),
        }
    
class Page(Model):
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