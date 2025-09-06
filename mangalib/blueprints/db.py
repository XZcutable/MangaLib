from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from datetime import datetime, timezone

import click, json

def init_app(app: Flask):
    db.init_app(app)
    # app.teardown_appcontext(close_all_db)
    app.cli.add_command(init_db)

@click.command('init-db')
def init_db():
    click.echo('Initializing database')
    db.create_all()


class Base(DeclarativeBase, MappedAsDataclass):
    def __getitem__(self, key):
        return getattr(self, key)

db = SQLAlchemy(model_class=Base)

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from mangalib.lib.enum import Access

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

class Manga(db.Model):
    id = Column(Integer, primary_key=True, nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    manga_path: Mapped[str] = mapped_column(nullable=False)
    pages: Mapped[int] = mapped_column(nullable=False)
    date_uploaded: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now(timezone.utc))

    def asDict(self):
        return {
            'title': self.title,
            'manga_path': self.manga_path,
            'pages': self.pages,
            'id': self.id,
            'date_uploaded': self.date_uploaded
        }

    def __repr__(self):
        return f'<Title {self.title}> (Pages: {len(json.loads(self.pages))}) ID {self.id} Uploaded: "{self.date_uploaded}"'
    
class Pages(db.Model):
    manga_id: Mapped[ForeignKey] = mapped_column(ForeignKey("manga.id"), primary_key=True)
    file_name: Mapped[str] = mapped_column(nullable=False)
    page_order: Mapped[int] = mapped_column(primary_key=True)
