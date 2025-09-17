from flask import (
    Flask, Blueprint, redirect, render_template, session, request, url_for, send_from_directory, send_file
)

from . import api
from .models import Manga, Chapter, Page, Path

from sqlalchemy import asc, desc

import os, random, json

image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')

bp = Blueprint('manga', __name__, url_prefix='/')

latest_count = 30
fetch_count = 15

def init_app(app: Flask):
    global latest_count, fetch_count

    hide_content(app.config["HIDE_MANGA"])
    hide_titles(app.config["HIDE_TITLES"])

    latest_count = app.config.get("LATEST_COUNT", latest_count)
    fetch_count = app.config.get("FETCH_COUNT", fetch_count)

@bp.route('/')
def home():
    clear_manga()
    return render_template('manga/home.html', titles=getLatest(count=30), HIDE_TITLES=HIDE_TITLES)

def fetchTitles(sort: str = 'asc', offset = 0, count = 30):
    query = Manga.query.filter(Manga.chapters).distinct(Manga.id)
    if sort == 'asc':
        query = query.order_by(asc(Manga.id))
    elif sort == 'desc':
        query = query.order_by(desc(Manga.id))

    query = query.offset(offset).limit(count)

    titles = executeMangaQuery(query)
    return titles

@bp.route('/latest')
def viewLatestTitles():
    return render_template('manga/directory.html', titles=fetchTitles('desc', 0, fetch_count), HIDE_TITLES=HIDE_TITLES)

@bp.route('/all')
def viewAllTitles():
    return render_template('manga/directory.html', titles=fetchTitles('asc', 0, fetch_count), HIDE_TITLES=HIDE_TITLES)

@bp.route('/random')
def random_manga():
    total = Manga.query.count()
    return redirect(f"{url_for('manga')}/{random.randrange(1,total)}/1")

@bp.route('/manga/<int:manga_id>')
@bp.route('/manga/<int:manga_id>/')
def manga_info(manga_id):
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for('home'))
    
    return render_template('manga/info.html', manga=manga, HIDE_TITLES=HIDE_TITLES)

@bp.route('/manga/<int:manga_id>/<int:page_number>')
@bp.route('/manga/<int:manga_id>/<int:page_number>/')
@bp.route('/manga/<int:manga_id>/<int:chapter_number>/<int:page_number>')
@bp.route('/manga/<int:manga_id>/<int:chapter_number>/<int:page_number>/')
def read_manga(manga_id, page_number=0, chapter_number=1):
    if page_number <= 0:
        return manga_info(manga_id=manga_id)
    
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for('home'))
    
    chapter: Chapter | None = Chapter.fromManga(manga=manga, number=chapter_number)
    if chapter is None:
        return redirect(f"{url_for('manga')}/{manga_id}")
    
    page: Page | None = Page.fromChapter(chapter, page_number)
    if page is None:
        return redirect(f"{url_for('manga')}/{manga_id}")
    
    return render_template('manga/page.html', manga=manga, chapter=chapter, page=page)


IMAGE_404 = lambda *_: send_file("static/images/error/404.png", max_age=10*24*60*60)

@bp.route('/manga-image/<int:manga_id>/<int:page_num>')
@bp.route('/manga-image/<int:manga_id>/<int:chapter_num>/<int:page_num>')
def get_manga_page(manga_id=None, page_num=None, chapter_num=1):
    # print("Geting page")
    if manga_id < 1 or page_num < 1 or chapter_num < 1:
        # print("Too Low")
        return IMAGE_404()
    
    manga: Manga | None = Manga.fromID(id=manga_id)
    if manga is None:
        return IMAGE_404()
    
    chapter: Chapter | None = Chapter.fromManga(manga=manga, number=chapter_num)
    if chapter is None:
        # print("Chapter Not Real")
        return IMAGE_404()
    
    page: Page | None = Page.fromChapter(chapter=chapter, number=page_num)
    if page is None:
        return IMAGE_404()
    
    return FETCH_PAGE(page)

def fetch_page(page: Page):
    if not os.path.exists(os.path.join(page.chapter.path, page.file_name)):
        return IMAGE_404()
    
    ext = os.path.splitext(page.file_name)[1]
    response = send_from_directory(page.chapter.path, page.file_name, download_name=f"{page.number}.{ext}", max_age=10*24*60*60)
    if response.status_code == 304:
        response.status_code = 200
    return response

FETCH_PAGE = fetch_page
def hide_content(hide: bool):
    global FETCH_PAGE

    if hide:
        FETCH_PAGE = IMAGE_404
    else:
        FETCH_PAGE = fetch_page


HIDE_TITLES = False
def hide_titles(hide: bool):
    global HIDE_TITLES

    HIDE_TITLES = hide

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

def clear_manga():
    session['current_manga'] = None
    session['current_chapter'] = None
    session['current_page'] = None

def getLatest(count = 10):
    latest = Manga.query.distinct(Manga.id).order_by(Manga.date_uploaded).limit(count).all()
    return latest

def executeMangaQuery(query):
    return [title for title in query.values(Manga.id, Manga.title)]

def getAllTitles(latest=False):
    query = Manga.query.filter(Manga.chapters).distinct(Manga.id)
    if latest:
        query = query.order_by(desc(Manga.id), desc(Manga.date_uploaded))
    else:
        query = query.order_by(asc(Manga.id))

    titles = executeMangaQuery(query)
    return titles

def createManga(dir, folderName):
    path = os.path.join(dir, folderName)
    if(not os.path.isdir(path)):
        print(f"Skipping {path}: Does not exist")
        return
    else:
        # print(f"Scanning {path}")
        pass
    
    
    folders: list = api.lsDirs(path)['folders']
    Path.sortList(folders)

    files: list = api.lsFiles(path, filters=image_types)['files']
    Path.sortList(files)

    manga = Manga.getOrUpdate(title=folderName, manga_path=path)
    chapters_to_add: list[Chapter] = []

    if(len(files) == 0 and len(folders) == 0):
        print(f"Empty Folder: {path}")
    
    files_scanned = False
    index = 1

    # The perfered way is to have no files in the base folder if there are chapters
    # and all the files if there is only chapter. But it would work regardless
    # Adds current folder to queue
    folders.insert(0, "")
       
    for folder in folders:
        chapter_path = os.path.join(path, folder)
        chapter_files: list = api.lsFiles(chapter_path, filters=image_types)['files']
        
        Path.sortList(chapter_files)

        chapter = createChapter(chapter_path, index, chapter_files)
        if(len(chapter_files) == 0):
            print(f"Empty Chapter: {chapter_path}")
        else:
            chapters_to_add.append(chapter)
            index += 1

    if index > 1:
        files_scanned = True

    if files_scanned:
        manga.chapters = chapters_to_add

    elif not files_scanned:
        if manga.new:
            pass
        else:
            print(f"Scanned an empty Manga: {path}")

    return manga


    
def createChapter(chapter_path: str, number: int, files: list):
    chapter: Chapter = Chapter(number=number, path=chapter_path)
    index = 1

    pages_to_add = []

    for file in files:
        page = Page(file_name=file, number=index)
        pages_to_add.append(page)
        index += 1

    chapter.pages = pages_to_add

    return chapter