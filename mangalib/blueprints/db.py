import sqlite3
import click
import os

from flask import current_app, g, Flask

def init_app(app: Flask):
    app.teardown_appcontext(close_all_db)

    app.cli.add_command(init_db_command)
    app.cli.add_command(init_user_db_command)
    app.cli.add_command(init_manga_db_command)

@click.command('init-db')
def init_db_command():
    init_user_db()
    init_manga_db()
    click.echo('Initialized all database')

@click.command('init-user-db')
def init_user_db_command():
    init_user_db()
    click.echo('Initialized user database')

@click.command('init-manga-db')
def init_manga_db_command():
    init_manga_db()
    click.echo('Initialized manga database')


def init_user_db():
    init_db('user_db', 'USER_DB', 'USER_SCHEMA')

def init_manga_db():
    init_db('manga_db', 'MANGA_DB', 'MANGA_SCHEMA')

def get_user_db():
    return get_db('user_db', 'USER_DB')

def get_manga_db():
    return get_db('manga_db', 'MANGA_DB')

def close_all_db(e=None):
    close_db('user_db')
    close_db('manga_db')

def close_db(db: str):
    db:sqlite3.Connection | None = g.pop(db, None)

    if db is not None:
        db.close()

def get_db(db: str, name: str) -> sqlite3.Connection:
    if db not in g:
        g.__setattr__(db, sqlite3.connect(
            os.path.join(current_app.instance_path, current_app.config[name]),
            detect_types=sqlite3.PARSE_DECLTYPES
        ))
        g.get(db).row_factory = sqlite3.Row
    
    return g.get(db)

def init_db(db: str, name: str, schema: str):
    db: sqlite3.Connection = get_db(db, name)

    with current_app.open_resource(os.path.join('schema', current_app.config[schema])) as f:
        data: bytes = f.read()
        db.executescript(data.decode())