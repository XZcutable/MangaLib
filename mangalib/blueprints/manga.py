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
    return render_template('manga/home.html', titles=getLatest(count=30))

@bp.route('/latest')
def viewLatestTitles():
    return render_template('manga/directory.html', titles=getAllTitles(latest=True))

@bp.route('/all')
def viewAllTitles():
    return render_template('manga/directory.html', titles=getAllTitles())

@bp.route('/random')
def random_manga():
    mangas = Manga.query.all()
    random_manga_id = random.randrange(1, len(mangas))
    return redirect(f"{url_for('manga')}/{random_manga_id}/1")

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
    
    manga = getMangaById(manga_id)
    current_chapter = getChapterByMangaAndNumber(manga_id=manga_id, chapter_number=chapter)

    if manga is None or current_chapter is None:
        return redirect(url_for('home'))
    
    current_manga = get_current_manga()

    if current_manga is None or current_manga != manga_id:
        current_manga = set_current_manga(manga)

    next_page = page + 1
    prev_page = page - 1

    if prev_page <= 0:
        if chapter > 1:
            last_chapter = getChapterByMangaAndNumber(manga_id=manga_id, chapter_number=chapter - 1)
            prev_page = f"{url_for('manga')}/{manga_id}/{last_chapter.number}/{len(last_chapter.pages)}"
        else:
            prev_page = None
    else:
        prev_page = f"{url_for('manga')}/{manga_id}/{chapter}/{prev_page}"

    if next_page > len(current_chapter.pages):
        next_chapter = getChapterByMangaAndNumber(manga_id=manga_id, chapter_number=chapter + 1)
        if next_chapter:
            next_page = f"{url_for('manga')}/{manga_id}/{chapter+1}/1"
        else:
            next_page = f"{url_for('manga')}/{manga_id}"
    else:
        next_page = f"{url_for('manga')}/{manga_id}/{chapter}/{next_page}"

    page_image = f"{url_for('manga-image')}/{manga_id}/{chapter}/{page}"
    
    return render_template('manga/page.html', manga_title=manga.title, current_page=page, next_page=next_page, prev_page=prev_page, page_image=page_image, total_pages=len(current_chapter.pages))
    
@bp.route('/manga-image/<int:manga_id>/<int:page_num>')
@bp.route('/manga-image/<int:manga_id>/<int:chapter_num>/<int:page_num>')
def get_manga_page(manga_id, page_num, chapter_num=1):
    # print("Geting page")
    if manga_id < 1 or page_num < 1 or chapter_num < 1:
        # print("Too Low")
        return None
    
    manga: Manga | None = getMangaById(id=manga_id)
    if manga is None:
        # print("Manga Not Real")
        return None
    
    chapter: Chapter | None = getChapterByMangaAndNumber(manga_id=manga_id, chapter_number=chapter_num)
    if chapter is None:
        # print("Chapter Not Real")
        return None
    
    page: Page | None = getPageByChapterAndNumber(chapter=chapter, page_number=page_num)
    if page is None:
        # print("Page Not Real")
        return None
    
    ext = os.path.splitext(page.file_name)[1]
    response = send_from_directory(chapter.path, page.file_name, download_name=f"{page_num}.{ext}", max_age=10*24*60*60)
    if response.status_code == 304:
        response.status_code = 200
    return response



@bp.route('/upload', methods=('GET', 'POST'))
def upload():
    pass

def set_current_manga(manga: Manga | None) -> Manga | None:
    if manga is None:
        clear_manga()
        return None
    else:
        session['current_manga'] = manga.id
        set_current_page(1)
        return manga

def get_current_manga() -> int:
    return session.get('current_manga', None)

def set_current_page(page: int):
    session['current_page'] = page

# def get_current_page() -> int | None:
#     session.get('current_page', None)

def clear_manga():
    session['current_manga'] = None
    session['current_chapter'] = None
    session['current_page'] = None

def getLatest(count = 10):
    latest = [title for title in Manga.query.filter(Manga.chapters).distinct(Manga.id).order_by(desc(Manga.date_uploaded), desc(Manga.id)).limit(count).values(Manga.id, Manga.title)]
    return latest

def getAllTitles(latest=False):
    query = Manga.query.filter(Manga.chapters).distinct(Manga.id)
    if latest:
        query = query.order_by(desc(Manga.id), desc(Manga.date_uploaded))
    else:
        query = query.order_by(asc(Manga.id))

    titles = [title for title in query.values(Manga.id, Manga.title)]
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
                db.session.delete(chapter)
                db.session.commit()
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
        # chapter.pages.append(page)
        # page =  Page.query.filter_by(manga_id=manga.id, number=number).one_or_404()
        return page
    else:
        page.chapter = chapter
        page.file_name = file_name
        return page
    
def getMangaById(id: int | None) -> Manga | None:
    if id is None:
        return None
    
    return Manga.query.filter_by(id=id).one_or_none()

def getChapterByMangaAndNumber(manga_id: int, chapter_number: int) -> Chapter | None:
    return Chapter.query.filter_by(manga_id=manga_id, number=chapter_number).one_or_none()

def getPageByChapterAndNumber(chapter: Chapter, page_number: int) -> Page | None:
    return Page.query.filter_by(number=page_number, chapter_path=chapter.path).one_or_none()