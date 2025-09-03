from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Flask
)

from datetime import datetime

from . import api
from .db import Manga, db

import os, json

image_types = ('.jpg', '.jpeg', '.png', '.webp')

bp = Blueprint('manga', __name__, url_prefix='/')

testLatest = [{'title_id': 0, 'title': 'test', 'uploader': 1, 'upload_date': datetime.now()}] * 10

@bp.route('/')
def home():
    return render_template('manga/home.html', latest=testLatest)

@bp.route('/manga/<manga_id>')
def render_manga_template():
    pass

@bp.route('/latest')
def latest():
    pass

@bp.route('/random')
def random():
    pass

@bp.route('/upload', methods=('GET', 'POST'))
def upload():
    pass

def getLatest(count = 10):
    # db = get_db()
    # latest = db.execute(
    #     'SELECT id, title, uploader'
    #     'FROM manga'
    #     'ORDER BY upload_date DESC'
    # ).fetchmany(count)
    return latest

def registerMangaPath(dir, folderName):
    path = os.path.join(dir, folderName)
    if(not os.path.isdir(path)):
        return
    
    print(f"Registering: {path}")
    pages = []
    for file in api.lsFiles(path)['files']:
        ext = os.path.splitext(file)[1]
        if ext in image_types:
            pages.append(os.path.join(path, file))

    # print(pages)
    manga: Manga | None = Manga.query.filter_by(title=folderName).first()
    if manga is None:
        manga: Manga = Manga(title=folderName, manga_path=path, pages=json.dumps(pages))
        db.session.add(manga)
        db.session.commit()
        print(manga)