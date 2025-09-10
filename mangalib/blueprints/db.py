from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Relationship, relationship

from datetime import datetime, timezone

import click, json

from sqlalchemy import Column, Integer, String, ForeignKey, MetaData, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from mangalib.lib.enum import Access


class Base(DeclarativeBase, MappedAsDataclass):
    def __getitem__(self, key):
        return getattr(self, key)
    pass

db = SQLAlchemy(model_class=Base)

def init_app(app: Flask):
    if app.config.get("SQLALCHEMY_DATABASE_URI", None) is None:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{app.config.get('DATABASE_PATH', '')}/database.db"

    db.init_app(app)
    app.cli.add_command(init_db)

@click.command('init-db')
def init_db():
    click.echo('Initializing database')
    db.create_all()

class Path(db.Model):
    path: Mapped[str] = mapped_column(primary_key=True)

# Username, passwords, preferences
class Users(db.Model):
    id = Column(Integer, primary_key=True, nullable=False)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(nullable=False, default="")
    approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    role: Mapped[str] = mapped_column(nullable=False, default=Access.USER.toString())
    date_created: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Name {self.username}>  ID {self.id} ({self.email}) Created "{self.date_created}" <approved: {self.approved}>'

# Manga, Chapters, Pages, metadata
class Manga(db.Model):
    id = Column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column()
    path: Mapped[str] = mapped_column()

    chapters: Mapped[list["Chapter"]] = relationship()

    date_uploaded: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'[Title {self.title}> (ID {self.id}), Chapters=<{self.chapters}'

class Chapter(db.Model):
    number: Mapped[int] = mapped_column(primary_key=True)
    manga_id: Mapped["Manga"] = mapped_column(ForeignKey("manga.id"), primary_key=True)
    #TODO Add Manga?
    # manga: Mapped["Manga"] = relationship(foreign_keys=[manga_id], back_populates="chapters")

    path: Mapped[str] = mapped_column()
    pages: Mapped[list["Page"]] = relationship()

    title: Mapped[str] = mapped_column(default="")

    def __repr__(self):
        return f"<Chapter {self.number}> (Pages {len(self.pages)})"

class Page(db.Model):
    number: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column()

    chapter_path = Column(Integer, primary_key=True)
    chapter_number = Column(Integer)

    chapter: Mapped["Chapter"] = relationship(foreign_keys=[chapter_path, chapter_number], back_populates="pages")

    __table_args__ = (
        ForeignKeyConstraint(
            [chapter_path, chapter_number], ["chapter.path", "chapter.number"]
        ),
    )

    def __repr__(self):
        return f"<Page {self.number}. name={self.file_name}"

class Metadata():
    pass