import sqlite3
import click
import os

from flask import current_app, g, Flask

from mangalib.models.db_base import db

def init_app(app: Flask):
    db.init_app(app)
    # app.teardown_appcontext(close_all_db)
    app.cli.add_command(init_db)

@click.command('init-db')
def init_db():
    click.echo('Initializing database')
    db.create_all()
