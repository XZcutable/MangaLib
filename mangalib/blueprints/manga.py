from flask import (
    Blueprint, redirect, render_template, session, url_for, send_from_directory, stream_template
)

from . import api
from .models import Manga, Chapter, Page, Path

from sqlalchemy import asc, desc

import os, random

image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')

bp = Blueprint('manga', __name__, url_prefix='/')

@bp.route('/')
def home():
    clear_manga()
    return render_template('manga/home.html', titles=getLatest(count=30))

@bp.route('/latest')
def viewLatestTitles():
    return render_template('manga/directory.html', titles=getAllTitles(latest=True))

@bp.route('/all')
def viewAllTitles():
    return render_template('manga/directory.html', titles=getAllTitles())

@bp.route('/random')
def random_manga():
    total = Manga.query.count()
    return redirect(f"{url_for('manga')}/{random.randrange(1,total)}/1")

@bp.route('/manga/<int:manga_id>')
@bp.route('/manga/<int:manga_id>/')
@bp.route('/manga/<int:manga_id>/<int:page_number>')
@bp.route('/manga/<int:manga_id>/<int:page_number>/')
@bp.route('/manga/<int:manga_id>/<int:chapter_number>/<int:page_number>/')
def read_manga(manga_id, page_number=None, chapter_number=1):
    if page_number is None:
        return redirect(url_for('home')) # TODO change to landing page
    elif page_number <= 0:
        return redirect(f"{url_for('manga')}/{manga_id}")
    
    current_manga: Manga | None = Manga.fromID(manga_id)
    current_chapter: Chapter | None = Chapter.fromManga(manga=current_manga, number=chapter_number)

    if current_manga is None or current_chapter is None:
        return redirect(url_for('home'))
    
    next_page = page_number + 1
    prev_page = page_number - 1

    if prev_page <= 0:
        if chapter_number > 1:
            last_chapter: Chapter | None = Chapter.fromManga(manga=current_manga, number=chapter_number - 1)
            prev_page = f"{url_for('manga')}/{manga_id}/{last_chapter.number}/{len(last_chapter.pages)}"
        else:
            prev_page = None
    else:
        prev_page = f"{url_for('manga')}/{manga_id}/{chapter_number}/{prev_page}"

    if next_page > len(current_chapter.pages):
        next_chapter: Chapter | None = Chapter.fromManga(manga=current_manga, number=chapter_number + 1)
        if next_chapter:
            next_page = f"{url_for('manga')}/{manga_id}/{chapter_number+1}/1"
        else:
            next_page = f"{url_for('manga')}/{manga_id}"
    else:
        next_page = f"{url_for('manga')}/{manga_id}/{chapter_number}/{next_page}"

    page_image = f"{url_for('manga-image')}/{manga_id}/{chapter_number}/{page_number}"
    
    return render_template('manga/page.html', manga_title=current_manga.title, current_page=page_number, next_page=next_page, prev_page=prev_page, page_image=page_image, total_pages=len(current_chapter.pages))
    
@bp.route('/manga-image/<int:manga_id>/<int:page_num>')
@bp.route('/manga-image/<int:manga_id>/<int:chapter_num>/<int:page_num>')
def get_manga_page(manga_id, page_num, chapter_num=1):
    # print("Geting page")
    if manga_id < 1 or page_num < 1 or chapter_num < 1:
        # print("Too Low")
        return None
    
    manga: Manga | None = Manga.fromID(id=manga_id)
    if manga is None:
        return None
    
    chapter: Chapter | None = Chapter.fromManga(manga=manga, number=chapter_num)
    if chapter is None:
        # print("Chapter Not Real")
        return None
    
    page: Page | None = Page.fromChapter(chapter=chapter, number=page_num)
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

def clear_manga():
    session['current_manga'] = None
    session['current_chapter'] = None
    session['current_page'] = None

def getLatest(count = 10):
    latest = Manga.query.distinct(Manga.id).order_by(Manga.date_uploaded).limit(count).all()
    return latest

def getAllTitles(latest=False):
    query = Manga.query.filter(Manga.chapters).distinct(Manga.id)
    if latest:
        query = query.order_by(desc(Manga.id), desc(Manga.date_uploaded))
    else:
        query = query.order_by(asc(Manga.id))

    titles = [title for title in query.values(Manga.id, Manga.title)]
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
        
        # if manga.new:
        #     db.session.add(manga)

    elif not files_scanned:
        if manga.new:
            pass
        else:
            print(f"Scanned an empty Manga: {path}")
            # db.session.delete(manga)

    # db.session.commit()

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