from flask import (
    Flask, Blueprint, redirect, render_template, request, url_for, send_from_directory, send_file, g
)

from . import api
from .models import db, Manga, Chapter, Page, Path, UserMangaData, MangaMetadata, ContentTag
from .auth import get_role_context

from sqlalchemy import func, select, and_, or_
from sqlalchemy import Select

import os, re

image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')

bp = Blueprint('manga', __name__, url_prefix='/manga')

latest_count = 30
fetch_count = 15

def init_app(app: Flask):
    global latest_count, fetch_count

    hide_content(app.config["HIDE_MANGA"])
    hide_titles(app.config["HIDE_TITLES"])

    latest_count = app.config.get("LATEST_COUNT", latest_count)
    fetch_count = app.config.get("FETCH_COUNT", fetch_count)

    @app.route('/')
    def index():
        return render_template('manga/home.html', titles=getLatest(count=30), HIDE_TITLES=HIDE_TITLES)

@bp.route('/home')
def home():
    return redirect(url_for("index"))

def fetchTitles(sort: str = 'asc', offset = 0, count = 30):
    # query = Manga.query.filter(Manga.chapters).distinct(Manga.id)
    query = select(Manga.id, Manga.title)
    if sort == 'asc':
        query = query.order_by(Manga.id.asc())
    elif sort == 'desc':
        query = query.order_by(Manga.id.desc())

    query = query.offset(offset)


    if count > 0:
        query = query.limit(min(count, 100))

    return [{ "id": result[0], "title": result[1] } for result in db.session.execute(query)]

@bp.route('/latest')
def latest():
    return render_template('manga/manga_infinite_scroll.html', sort='desc', title="Latest", HIDE_TITLES=HIDE_TITLES)

@bp.route('/all')
def all():
    return render_template('manga/manga_infinite_scroll.html', sort='asc', title="All", HIDE_TITLES=HIDE_TITLES)

@bp.route('/history')
def history():
    return render_template('manga/history.html', sort='desc', title="History", HIDE_TITLES=HIDE_TITLES)

@bp.route('/random')
def random_manga():
    manga = Manga.query.order_by(func.random()).first() 
    return redirect(f"{url_for('manga.resume')}/{manga.id}")

@bp.route('/random-unread')
def random_unread():
    user_read = [ row.manga_id for row in UserMangaData.query.filter_by(is_read = True).values(UserMangaData.manga_id)]
    manga: Manga = Manga.query.filter(Manga.id.not_in(user_read)).order_by(func.random()).first()
    if manga is None:
        return random_manga()
    return redirect(f"{url_for('manga.resume')}/{manga.id}")

@bp.route('')
@bp.route('/<int:manga_id>')
def info(manga_id: int):
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for('home'))
    
    user_manga_data: UserMangaData = UserMangaData.getOrCreate(api.getUserID(), manga)

    return render_template('manga/info.html', manga=manga.toJson(), user_manga_data=user_manga_data.toJson(), HIDE_TITLES=HIDE_TITLES, **get_role_context())

@bp.route("/resume")
@bp.route("/resume/<int:manga_id>")
@bp.route("/resume/<int:manga_id>/<int:chapter_number>")
def resume(manga_id: int, chapter_number: int=0):
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for('home'))
    progress: UserMangaData = UserMangaData.getOrCreate(g.user["id"], manga)

    progress_data = { "manga_id": manga.id, "page_number": progress.current_page, "chapter_number": progress.current_chapter }
    if chapter_number <= 0 and progress.new:
        progress_data = { "manga_id": manga.id, "page_number": 1, "chapter_number": 1 }
    elif chapter_number > 0 and (progress.new or chapter_number != progress.current_chapter):
        progress_data = { "manga_id": manga.id, "page_number": 1, "chapter_number": chapter_number }

    return redirect(url_for("manga.read", **progress_data))

@bp.route('')
@bp.route('/<int:manga_id>/<int:page_number>')
@bp.route('/<int:manga_id>/<int:chapter_number>/<int:page_number>')
def read(manga_id: int, page_number=0, chapter_number=1):
    if page_number <= 0:
        return info(manga_id=manga_id)
    
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for('home'))
    
    chapter: Chapter | None = Chapter.fromManga(manga=manga, number=chapter_number)
    if chapter is None:
        return redirect(f"{url_for('manga.info')}/{manga_id}")
    
    page: Page | None = Page.fromChapter(chapter, page_number)
    if page is None:
        return redirect(f"{url_for('manga.info')}/{manga_id}")
    
    return render_template('manga/page.html', manga=manga.toJson(), chapter=chapter.toJson(), page=page.toJson())

IMAGE_404 = lambda *_: send_file("static/assets/images/error/404.png", max_age=10*24*60*60)

@bp.route('/manga-image')
@bp.route('/manga-image/<int:manga_id>/<int:page_num>')
@bp.route('/manga-image/<int:manga_id>/<int:chapter_num>/<int:page_num>')
def image(manga_id=None, page_num=None, chapter_num=1):
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


@bp.route('/upload', methods=('GET', 'POST'))
def upload():
    pass

TERM_PATTERN = re.compile(r"(?<![:\"'])\b\w+\b(?![:\"'])")
TAG_PATTERN = re.compile(r"(?<!\w|!)tag:(\w+)")
NTAG_PATTERN = re.compile(r"!tag:(\w+)")
DQUOTE_PATTERN = re.compile(r"\"(.*?)\"")
QUOTE_PATTERN = re.compile(r"'(.*?)'")

READ = "read"
TAGGED = "tagged"
IN_PROGRESS = "progress"
NSFW = "nsfw"

@bp.route("/search")
def search():
    q = request.args.get('q')
    if q is None:
        return render_template("manga/search.html", results=[])
    
    q = q.lower()
    terms = [*TERM_PATTERN.findall(q), *[*DQUOTE_PATTERN.findall(q), *QUOTE_PATTERN.findall(q)]]
    tags = TAG_PATTERN.findall(q)
    ntags = NTAG_PATTERN.findall(q)

    query = (
        select(Manga.id, Manga.title)
        .join(MangaMetadata, MangaMetadata.manga_id == Manga.id)
    )

    def handle_special_tag(tag, stmt, nstmt):
        filter_stmt = tag in tags
        filter_nstmt = tag in ntags

        if filter_stmt != filter_nstmt:
            if filter_stmt:
                tags.pop(tags.index(tag))
                return stmt
            elif filter_nstmt:
                ntags.pop(ntags.index(tag))
                return nstmt

    def has_special_tag(tag):
        filter_stmt = tag in tags
        filter_nstmt = tag in ntags

        if filter_stmt and filter_nstmt:
            tags.pop(tags.index(tag))
            ntags.pop(ntags.index(tag))
        elif filter_stmt != filter_nstmt:
            return True
        
        return False

    def replace_symbols(ls: list[str]):
        for i in range(len(ls)):
            ls[i] = ls[i].replace("_", " ")


    user_id = None
    joined_user_data = False
    replace_symbols(terms)
    replace_symbols(tags)
    replace_symbols(ntags)

    # Doing it this way will only show titles the user has interacted with before and not others
    # I like this interaction and it is now intended behavior
    if has_special_tag(READ):
        user_id = user_id or api.getUserID()
        if not joined_user_data:
            query = query.join_from(Manga, UserMangaData, Manga.id == UserMangaData.manga_id and UserMangaData.user_id == user_id)
            joined_user_data = True

        filter_read = query.where(UserMangaData.is_read)
        filter_unread = query.where(~UserMangaData.is_read)
        query = handle_special_tag(READ, filter_read, filter_unread)

    if has_special_tag(TAGGED):
        filter_tagged = query.where(MangaMetadata.tags.any(ContentTag.tag != None))
        filter_untagged = query.where(~MangaMetadata.tags.any(ContentTag.tag != None))
        query = handle_special_tag(TAGGED, filter_tagged, filter_untagged)

    if has_special_tag(IN_PROGRESS):
        user_id = user_id or api.getUserID()
        if not joined_user_data:
            query = query.join_from(Manga, UserMangaData, and_(Manga.id == UserMangaData.manga_id, UserMangaData.user_id == user_id))
            joined_user_data = True

        filter_in_progress = query.where(and_(UserMangaData != None, UserMangaData.is_read == False, or_(UserMangaData.current_page > 1, UserMangaData.current_chapter > 1)))
        filter_no_progress = query.where(or_(UserMangaData == None, and_(UserMangaData.is_read == False, UserMangaData.current_page == 1, UserMangaData.current_chapter == 1)))
        query = handle_special_tag(IN_PROGRESS, filter_in_progress, filter_no_progress)

    if has_special_tag(NSFW):
        filter_nsfw = query.where(MangaMetadata.tags.any(ContentTag.nsfw))
        filter_sfw = query.where(~MangaMetadata.tags.any(ContentTag.nsfw))
        query = handle_special_tag(NSFW, filter_nsfw, filter_sfw)

    for term in terms:
        query = query.where(Manga.title.contains(term))

    if len(tags) > 0:
        query = query.where(MangaMetadata.tags.any(ContentTag.tag.in_(tags)))

    if len(ntags) > 0:
        query = query.where(~MangaMetadata.tags.any(ContentTag.tag.in_(ntags)))

    results = [{"id": result[0], "title": result[1]} for result in db.session.execute(query)]

    # print("Results:", results)

    return render_template("manga/search.html", results=results, HIDE_TITLES=HIDE_TITLES)

    

FETCH_PAGE = fetch_page
HIDE_MANGA = False
def hide_content(hide: bool):
    global FETCH_PAGE, HIDE_MANGA
    if hide:
        FETCH_PAGE = IMAGE_404
    else:
        FETCH_PAGE = fetch_page
    HIDE_MANGA = hide


HIDE_TITLES = False
def hide_titles(hide: bool):
    global HIDE_TITLES

    HIDE_TITLES = hide

def getLatest(count = 10):
    latest = Manga.query.distinct(Manga.id).order_by(Manga.date_uploaded.desc()).limit(count).all()
    return latest

def addOrUpdateManga(dir, folderName):
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

    manga = Manga.getOrCreate(title=folderName, manga_path=path)
    new_chapters: list[Chapter] = []

    if(len(files) == 0 and len(folders) == 0):
        print(f"Empty Folder: {path}")
    
    chapter_added = False
    next_chapter_number = len(manga.chapters) + 1

    # The perfered way is to have no files in the base folder if there are chapters
    # and all the files if there is only chapter. But it would work regardless
    # Adds current folder to queue
    folders.insert(0, "")
       
    for folder in folders:
        chapter_path = os.path.join(path, folder)
        chapter: Chapter = Chapter.getOrCreate(manga, chapter_path, next_chapter_number)
        
        chapter_files: list = api.lsFiles(chapter_path, filters=image_types)['files']

        if chapter.new:
            if(len(chapter_files) == 0):
                print(f"Empty Chapter: {chapter_path}")
            else:
                Path.sortList(chapter_files)
                addPagesToChapter(chapter, chapter_files)

                new_chapters.append(chapter)
                next_chapter_number += 1
        else:
            if(len(chapter_files) == 0):
                print(f"Empty Old Chapter: {chapter_path}")
                db.session.delete(chapter)
            elif(len(chapter.pages) == 0):
                print("Empty chapter in path:", chapter_path)
            else:
                Page.addPagesAndSort(chapter, chapter_files)


    if next_chapter_number > len(manga.chapters) + 1:
        chapter_added = True

    if chapter_added:
        manga.chapters.extend(new_chapters)

    elif not chapter_added:
        if manga.new:
            pass
        else:
            print(f"No change in Manga: {path}")

    return manga
    
def addPagesToChapter(chapter: Chapter, files: list):
    next_page_number = len(chapter.pages) + 1

    new_pages = []

    for file in files:
        page: Page = Page.getOrCreate(chapter=chapter, file_name=file, number=next_page_number)
        if page.new:
            new_pages.append(page)
            next_page_number += 1

    chapter.pages.extend(new_pages)

    return chapter