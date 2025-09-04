from flask import (
    Blueprint, redirect, render_template, request, session, url_for, send_file, send_from_directory
)

from datetime import datetime

from . import api
from .db import db, Manga, Pages

from sqlalchemy import text

import os, json

image_types = ('.jpg', '.jpeg', '.png', '.webp')

bp = Blueprint('manga', __name__, url_prefix='/')

testLatest = [{'title_id': 1, 'title': 'test', 'uploader': 1, 'upload_date': datetime.now()}] * 10

@bp.route('/')
def home():
    return render_template('manga/home.html', titles=getAllTitles())

@bp.route('/manga/<int:manga_id>')
@bp.route('/manga/<int:manga_id>/')
@bp.route('/manga/<int:manga_id>/<int:page>')
@bp.route('/manga/<int:manga_id>/<int:page>/')
def manga(manga_id, page=None):
    if page is None:
        return redirect(url_for('home'))
    elif page <= 0:
        return redirect(f"{url_for('manga')}/{manga_id}")
    elif not hasPage(manga_id, page):
        return redirect(f"{url_for('manga')}/{manga_id}")
    
    next_page = f"{url_for('manga')}/{manga_id}"
    if hasPage(manga_id, page + 1):
        next_page = f"{url_for('manga')}/{manga_id}/{page + 1}"

    page_image = f"{url_for('manga-image')}/{manga_id}/{page}"
    
    return render_template('manga/page.html', next_page=next_page, page_image=page_image)

def hasPage(manga_id, page):
    manga: Manga | None = Manga.query.filter_by(id=manga_id).first()
    if manga is None:
        return False
    
    page: Pages | None = Pages.query.filter_by(manga_id=manga_id, page_order=page).first()
    if page is None:
        return False
    
    return True
    
@bp.route('/manga-image/<int:manga_id>/<int:page>')
def get_manga_page(manga_id, page):
    manga: Manga | None = Manga.query.filter_by(id=manga_id).first()
    if manga is None:
        return None
    
    page: Pages | None = Pages.query.filter_by(manga_id=manga_id, page_order=page).first()
    if page is None:
        return None
    
    return send_from_directory(manga.manga_path, page.file_name)

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
    latest = db.session.execute(text(
        'SELECT id, title '
        'FROM manga '
        'ORDER BY date_uploaded ASC'
    )).fetchmany(count)
    return latest

def getAllTitles():
    titles = db.session.execute(text(
        'SELECT id, title '
        'FROM manga '
        'ORDER BY date_uploaded DESC'
    )).all()
    return titles

def registerMangaPath(dir, folderName):
    path = os.path.join(dir, folderName)
    if(not os.path.isdir(path)):
        return
    
    files = api.lsFiles(path)['files']
    if len(files) == 0:
        return
    
    manga: Manga | None = Manga.query.filter_by(title=folderName).first()
    if manga is None:
        print(f"Registering {folderName}")
        manga: Manga = Manga(title=folderName, manga_path=path)
        db.session.add(manga)
        manga: Manga = Manga.query.filter_by(title=folderName).first()
        print(manga.id)
    else:
        print(f"Updating {folderName}")

    # print(f"Registering {len(files)} pages to {folderName}")
    index = 1
    for file in files:
        ext = os.path.splitext(file)[1]
        if ext in image_types:
            page: Pages = Pages.query.filter_by(manga_id=manga.id, page_order=index).one_or_none()
            if page is None:
                page = Pages(manga_id=manga.id, file_name=file, page_order=index)
                db.session.add(page)
            else:
                page.file_name = file
            index += 1
    if index == 1:
        db.session.rollback()

    db.session.commit()
    