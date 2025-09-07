from flask import (
    Blueprint, redirect, render_template, request, session, url_for, send_from_directory, stream_template
)

from datetime import datetime

from . import api
from .db import db, Manga, Pages

from sqlalchemy import asc, desc

import os, random

image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')

bp = Blueprint('manga', __name__, url_prefix='/')

testLatest = [{'title_id': 1, 'title': 'test', 'uploader': 1, 'upload_date': datetime.now()}] * 10

@bp.route('/')
def home():
    clear_manga()
    return render_template('manga/home.html', titles=getAllTitles())

@bp.route('/manga/<int:manga_id>')
@bp.route('/manga/<int:manga_id>/')
@bp.route('/manga/<int:manga_id>/<int:page>')
@bp.route('/manga/<int:manga_id>/<int:page>/')
def read_manga(manga_id, page=None):
    if page is None:
        return redirect(url_for('home')) # TODO change to landing page
    elif page <= 0:
        return redirect(f"{url_for('manga')}/{manga_id}")
    
    manga = get_current_manga()

    if manga is None:
        manga = set_current_manga(manga_id)
    elif manga['id'] != manga_id:
        manga = set_current_manga(manga_id)

    if manga:
        next_page = page + 1
        prev_page = page - 1

        if prev_page <= 0:
            prev_page = None
        else:
            prev_page = f"{url_for('manga')}/{manga_id}/{prev_page}"

        if next_page > manga['pages']:
            next_page = f"{url_for('manga')}/{manga_id}"
        else:
            next_page = f"{url_for('manga')}/{manga_id}/{next_page}"

        page_image = f"{url_for('manga-image')}/{manga_id}/{page}"
        
        return render_template('manga/page.html', manga_title=manga['title'], current_page=page, next_page=next_page, prev_page=prev_page, page_image=page_image, total_pages=manga['pages'])
    else:
        return redirect(url_for('home')) # TODO Change to not found
    
@bp.route('/manga-image/<int:manga_id>/<int:page>')
def get_manga_page(manga_id, page):
    manga: Manga | None = Manga.query.filter_by(id=manga_id).first()
    if manga is None:
        return None
    
    page: Pages | None = Pages.query.filter_by(manga_id=manga_id, page_order=page).first()
    if page is None:
        return None
    
    ext = os.path.splitext(page.file_name)[1]
    response = send_from_directory(manga.manga_path, page.file_name, download_name=f"{page}{ext}", max_age=10*24*60*60)
    if response.status_code == 304:
        response.status_code = 200
    return response

@bp.route('/latest')
def latest():
    pass
    
    

@bp.route('/random')
def random_manga():
    mangas = Manga.query.all()
    random_manga_id = random.randrange(1, len(mangas))
    return redirect(f"{url_for('manga')}/{random_manga_id}/1")

@bp.route('/upload', methods=('GET', 'POST'))
def upload():
    pass

def set_current_manga(manga_id: int | None) -> dict[str, any]:
    if manga_id is None:
        clear_manga()
        return None
    else:
        manga: Manga | None = Manga.query.filter_by(id=manga_id).one_or_none()

        if manga is None:
            return None
        session['current_manga'] = manga.asDict()
        set_current_page(1)
        return session['current_manga']

def get_current_manga() -> dict[str, any]:
    return session.get('current_manga', None)

def set_current_page(page: int):
    session['current_page'] = page

def get_current_page() -> int | None:
    session.get('current_page', None)

def clear_manga():
    session['current_manga'] = None
    session['current_page'] = None

def getLatest(count = 10):
    latest = Manga.query.order_by(Manga.date_uploaded, desc(Manga.id)).limit(10).values(Manga.id, Manga.title)
    latest = [title for title in latest] # TODO get the first 10
    return latest

def getAllTitles():
    titles = [title for title in Manga.query.values(Manga.id, Manga.title)]
    titles.sort(key=lambda manga: manga.id)
    return titles

def registerMangaPath(dir, folderName):
    path = os.path.join(dir, folderName)
    if(not os.path.isdir(path)):
        return
    
    files: list = api.lsFiles(path)['files']
    if len(files) == 0:
        return
    
    files.sort(key=str.casefold)
    files.sort(key=lambda name: len(name))
    
    manga: Manga | None = Manga.query.filter_by(title=folderName).first()
    if manga is None:
        # print(f"Registering {folderName}")
        manga: Manga = Manga(title=folderName, manga_path=path, pages=0)
        db.session.add(manga)
        manga: Manga = Manga.query.filter_by(title=folderName).first()
        # print(manga.id)
    else:
        # print(f"Updating {folderName}")
        manga.manga_path = path

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
    else:
        manga.pages = index - 1

    db.session.commit()
    