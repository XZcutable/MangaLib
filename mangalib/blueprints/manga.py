from flask import (
    Blueprint, redirect, render_template, request, session, url_for, send_from_directory, stream_template
)

from datetime import datetime

from . import api
from .db import db, Manga, Chapter, Page

from sqlalchemy import asc, desc, ForeignKey, text

import os, random

image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')

bp = Blueprint('manga', __name__, url_prefix='/')

testLatest = [{'title_id': 1, 'title': 'test', 'uploader': 1, 'upload_date': datetime.now()}] * 10

@bp.route('/')
def home():
    # clear_manga()
    return render_template('manga/home.html', titles=getLatest())

@bp.route('/manga/<int:manga_id>')
@bp.route('/manga/<int:manga_id>/')
@bp.route('/manga/<int:manga_id>/<int:page>')
@bp.route('/manga/<int:manga_id>/<int:page>/')
@bp.route('/manga/<int:manga_id>/<int:chapter>/<int:page>/')
def read_manga(manga_id, page=None, chapter=1):
    if page is None:
        return redirect(url_for('home')) # TODO change to landing page
    elif page <= 0:
        return redirect(f"{url_for('manga')}/{manga_id}")
    
    # manga = get_current_manga()

    # if manga is None:
    #     manga = set_current_manga(manga_id)
    # elif manga['id'] != manga_id:
    #     manga = set_current_manga(manga_id)

    # if manga:
    #     next_page = page + 1
    #     prev_page = page - 1

    #     if prev_page <= 0:
    #         prev_page = None
    #     else:
    #         prev_page = f"{url_for('manga')}/{manga_id}/{prev_page}"

    #     if next_page > manga['pages']:
    #         next_page = f"{url_for('manga')}/{manga_id}"
    #     else:
    #         next_page = f"{url_for('manga')}/{manga_id}/{next_page}"

    page_image = f"{url_for('manga-image')}/{manga_id}/{chapter}/{page}"
    
    return render_template('manga/page.html', manga_title="TO FIX", current_page=page, next_page=page+1, prev_page=page-1, page_image=page_image, total_pages=0)
    # return render_template('manga/page.html', manga_title=manga['title'], current_page=page, next_page=next_page, prev_page=prev_page, page_image=page_image, total_pages=manga['pages'])
    # else:
        # return redirect(url_for('home')) # TODO Change to not found
    
@bp.route('/manga-image/<int:manga_id>/<int:page_num>')
@bp.route('/manga-image/<int:manga_id>/<int:chapter_num>/<int:page_num>')
def get_manga_page(manga_id, page_num, chapter_num=1):
    if manga_id < 1 or page_num < 1 or chapter_num < 1:
        return None
    
    manga: Manga | None = Manga.query.filter_by(id=manga_id).one_or_none()
    if manga is None:
        return None
    
    chapter: Chapter | None = Chapter.query.filter_by(manga_id=manga.id, number=chapter_num).one_or_none()
    if chapter is None:
        return None
    
    page: Page | None = Page.query.filter_by(number=page_num, chapter_path=chapter.path).one_or_none()
    if page is None:
        return None
    
    ext = os.path.splitext(page.file_name)[1]
    response = send_from_directory(chapter.path, page.file_name, download_name=f"{page_num}.{ext}", max_age=10*24*60*60)
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

# def set_current_manga(manga_id: int | None) -> dict[str, any]:
#     if manga_id is None:
#         clear_manga()
#         return None
#     else:
#         manga: Manga | None = Manga.query.filter_by(id=manga_id).one_or_none()

#         if manga is None:
#             return None
        
#         session['current_manga'] = manga
#         set_current_page(1)
#         return session['current_manga']

# def get_current_manga() -> dict[str, any]:
#     return session.get('current_manga', None)

# def set_current_page(page: int):
#     session['current_page'] = page

# def get_current_page() -> int | None:
#     session.get('current_page', None)

# def clear_manga():
#     session['current_manga'] = None
#     session['current_page'] = None

def getLatest(count = 10):
    latest = Manga.query.order_by(Manga.date_uploaded, desc(Manga.id)).filter(Manga.chapters).limit(10).values(Manga.id, Manga.title)
    latest = [title for title in latest] # TODO get the first 10
    return latest

def getAllTitles():
    titles = [title for title in Manga.query.filter(Manga.chapters > 0).values(Manga.id, Manga.title)]
    titles.sort(key=lambda manga: manga.id)
    return titles

def scanMangaPath(dir, folderName):
    path = os.path.join(dir, folderName)
    if(not os.path.isdir(path)):
        print(f"Skipping {path}: Does not exist")
        return
    else:
        # print(f"Scanning {path}")
        pass
    
    
    folders: list = api.lsDirs(path)['folders']
    folders.sort(key=str.casefold)
    folders.sort(key=lambda name: len(name))

    files: list = api.lsFiles(path, filters=image_types)['files']
    files.sort(key=lambda name: str.casefold(os.path.splitext(name)[0]))
    files.sort(key=lambda name: len(name))

    manga = updateOrSetManga(title=folderName, manga_path=path)

    if(len(files) == 0 and len(folders) == 0):
        print(f"Empty Folder: {path}")
    
    files_scanned = False
    index = 1
    
    # The perfered way is to have no files in the base folder if there are chapters
    if len(files) > 0:
        scanToChapter(manga, path, index, files)
        # manga.pages = len(files)
        files_scanned = True
        index += 1
    # else:
        # print("Implement multile chapters")
        # db.session.rollback()
        # return


    for folder in folders:
        chapter_path = os.path.join(path, folder)
        chapter_files: list = api.lsFiles(chapter_path, filters=image_types)['files']
        
        db.session.begin_nested()
        
        chapter = scanToChapter(manga, chapter_path, index, chapter_files)
        if(len(chapter_files) == 0):
            print(f"Empty Chapter: {chapter_path}")
            if chapter.new:
                db.session.rollback()
            else:
                db.session.commit()
                index += 1
        else:
            index += 1
            db.session.commit()
    
    if index > 1:
        # manga.chapters = index - 1
        files_scanned = True

    if not files_scanned:
        if manga.new:
            db.session.rollback()
        else:
            print(f"Scanned an empty Manga: {path}")
            manga.chapters = 0

    db.session.commit()

def updateOrSetManga(title, manga_path):
    # print(f"Getting: {title}")
    manga = Manga.query.filter_by(title=title, path=manga_path).one_or_none()
    if manga is None:
        manga = Manga(title=title, path=manga_path, chapters = list())
        db.session.add(manga)
        manga: Manga = Manga.query.filter_by(title=manga.title).one_or_404()
        manga.new = True
        return manga
    else:
        manga.new = False
        manga.path = manga_path
        return manga

def updateOrUpdateChapter(manga: Manga, chapter_path: str, number: int):
    # print(f"Looking for Chapter {chapter_path} ({number})")
    chapter: Chapter | None = Chapter.query.filter_by(manga_id=manga.id, number=number).one_or_none()
    if chapter is None:
        chapter = Chapter(manga_id=manga.id, number=number, path=chapter_path, pages=list())
        db.session.add(chapter)
        manga.chapters.append(chapter)
        # chapter = Chapter.query.filter_by(manga=manga, number=chapter.number).one_or_404()
        chapter.new = True
        return chapter
    else:
        chapter.path = chapter_path
        # chapter.number = number
        chapter.new = False
        return chapter
    
def scanToChapter(manga: Manga, chapter_path: str, number: int, files: list):
    chapter = updateOrUpdateChapter(manga, chapter_path, number)
    index = 1
    for file in files:
        updateOrGetPage(manga, chapter, file, index)
        index += 1

    manga.pages = index - 1
    # Page.query.filter_by(manga_id=manga.id).filter(number > Page.number).delete()

    return chapter
    # print(f"Scanned {manga.pages} pages to chapter {number}")

def updateOrGetPage(manga: Manga, chapter: Chapter, file_name: str, number: int):
    page: Page = Page.query.filter_by(number=number, chapter_path=chapter.path).one_or_none()
    if page is None:
        # print(manga, chapter, file_name, number)
        page = Page(chapter=chapter, file_name=file_name, number=number)
        db.session.add(page)
        # page =  Page.query.filter_by(manga_id=manga.id, number=number).one_or_404()
        return page
    else:
        page.file_name = file_name
        return page