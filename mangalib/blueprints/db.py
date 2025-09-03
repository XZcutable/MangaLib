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

from sqlalchemy import Column, Integer
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
    pages: Mapped[str] = mapped_column(nullable=False, default="{}")
    user_score_total: Mapped[int] = mapped_column(nullable=False, default=0)
    user_score_count: Mapped[int] = mapped_column(nullable=False, default=0)
    rating: Mapped[str] = mapped_column(nullable=False, default="unrated")
    date_uploaded: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Title {self.title}> (Pages: {len(json.loads(self.pages))}) ID {self.id} Uploaded: "{self.date_uploaded}"'