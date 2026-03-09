from flask import (
    Flask, Blueprint, redirect, render_template, request, url_for, send_from_directory, send_file, g
)

from ..blueprints import api
from ..models import Manga, Chapter, Page, UserMangaData
from ..database import db
from ..auth import get_role_context
from ..constants import VAR, HTML, ROUTE, ENDPOINT
from ..quries import QUERY_FAVORITES, QUERY_HISTORY, QUERY_QUEUE

from sqlalchemy import func, select, exc

import os, re, zipfile, pymupdf, io

image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')
archive_types = ('.cbz', '.zip', '.pdf')

bp = Blueprint('manga', __name__, url_prefix='/manga')

def init_app(app: Flask):
    hide_content(app.config[VAR.HIDE_MANGA])
    hide_titles(app.config[VAR.HIDE_TITLES])
    
def home():
    random_query = (
        select(Manga)
        .order_by(func.random())
        .limit(30)
    )
    random_titles = db.session.scalars(random_query).all()
    return render_template(HTML.HOME, titles=random_titles, COUNT=db.Manga.MANGA_COUNT, HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.LATEST)
def latest_titles():
    return render_template(HTML.INFINITE_SCROLL, sort=VAR.DESC, title="Latest", COUNT=db.Manga.MANGA_COUNT, HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.ALL)
def all_titles():
    return render_template(HTML.INFINITE_SCROLL, sort=VAR.ASC, title="All", COUNT=db.Manga.MANGA_COUNT, HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.HISTORY)
def history():
    user_id = db.session.getUserID()
    query = QUERY_HISTORY(user_id)
    query = select(func.count()).select_from(query)

    count = db.session.scalar(query)
    return render_template(HTML.HISTORY, sort=VAR.DESC, COUNT=count, title="History", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.FAVORITES)
def favorites():
    user_id = db.session.getUserID()
    query = QUERY_FAVORITES(user_id)
    query = select(func.count()).select_from(query)

    count = db.session.scalar(query)
    return render_template(HTML.FAVORITES, sort=VAR.DESC, COUNT=count, title="Favorites", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.QUEUED)
def queued():
    user_id = db.session.getUserID()
    query = QUERY_QUEUE(user_id)
    query = select(func.count()).select_from(query)

    count = db.session.scalar(query)
    return render_template(HTML.QUEUED, sort=VAR.DESC, COUNT=count, title="To Read", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.RANDOM)
def random_manga():
    random_id = db.session.scalar(select(Manga.id).order_by(func.random()))
    if random_id is None:
        return redirect(url_for(ENDPOINT.HOME))
    else:
        return redirect(f"{url_for(ENDPOINT.MANGA_RESUME, manga_id=random_id)}")

@bp.route(ROUTE.RANDOM_UNREAD)
def random_unread():
    user_id = db.session.getUserID()
    random_unread_query = (
        select(Manga.id).outerjoin(UserMangaData, UserMangaData.user_id == user_id)
        .where((UserMangaData.is_read == None) | (~UserMangaData.is_read))
        .order_by(func.random())
    )
    random_id = db.session.scalar(random_unread_query)
    if random_id is None:
        return random_manga()
    return redirect(f"{url_for(ENDPOINT.MANGA_RESUME, manga_id=random_id)}")

@bp.route('/<int:manga_id>')
def info(manga_id: int = None):
    manga: Manga | None = db.Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    
    if len(manga.chapters) > 0:
        user_manga_data: UserMangaData = db.UserMangaData.getOrCreate(db.session.getUserID(), manga)
        chapter = request.args.get('chapter')
        if chapter is None or not str.isdigit(chapter) or int(chapter) < 1:
            chapter = manga.chapters[0]
        else:
            chapter = manga.chapters[int(chapter)-1]

        return render_template(HTML.INFO, manga=manga.toJson(), chapter=chapter.toJson(), user_manga_data=user_manga_data.toJson(), HIDE_TITLES=HIDE_TITLES, **get_role_context())
    else:
        return render_template(HTML.INFO, manga=manga.toJson(), chapter={}, user_manga_data={}, HIDE_TITLES=HIDE_TITLES, **get_role_context())

@bp.route("/resume/<int:manga_id>")
@bp.route("/resume/<int:manga_id>/<int:chapter_number>")
def resume(manga_id: int, chapter_number: int=0):
    manga: Manga | None = db.Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    progress: UserMangaData = db.UserMangaData.getOrCreate(g.user["id"], manga)

    progress_data = { "manga_id": manga.id, "page_number": progress.current_page, "chapter_number": progress.current_chapter }
    if chapter_number <= 0 and progress.new:
        progress_data = { "manga_id": manga.id, "page_number": 1, "chapter_number": 1 }
    elif chapter_number > 0 and (progress.new or chapter_number != progress.current_chapter):
        progress_data = { "manga_id": manga.id, "page_number": 1, "chapter_number": chapter_number }

    return redirect(url_for(ENDPOINT.MANGA_READ, **progress_data))

@bp.route('/<int:manga_id>/<int:page_number>')
@bp.route('/<int:manga_id>/<int:chapter_number>/<page_number>')
def read(manga_id: int, page_number=0, chapter_number=1):  
    manga: Manga | None = db.Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    
    chapter: Chapter | None = db.Chapter.fromManga(manga=manga, number=chapter_number)
    if chapter is None:
        return redirect(f"{url_for(ENDPOINT.MANGA_INFO, manga_id=manga_id)}")
    
    if page_number == "last":
        return redirect(f"{url_for(ENDPOINT.MANGA_READ, manga_id=manga_id, chapter_number=chapter_number, page_number=len(chapter.pages))}")
    elif type(page_number) == str and str.isdigit(page_number):
        page_number = int(page_number)
    if page_number <= 0:
        return info(manga_id=manga_id)
        
    page: Page | None = db.Page.fromChapter(chapter, page_number)
    if page is None:
        return redirect(f"{url_for(ENDPOINT.MANGA_INFO, manga_id=manga_id)}")
    
    return render_template(HTML.PAGE, manga=manga.toJson(), chapter=chapter.toJson(), page=page.toJson())

IMAGE_404 = lambda *_: send_file("static/assets/images/error/404.png", max_age=10*24*60*60)

@bp.route('/manga-image/<int:manga_id>/<int:page_number>')
@bp.route('/manga-image/<int:manga_id>/<int:chapter_number>/<int:page_number>')
def image(manga_id=None, page_number=None, chapter_number=1):
    # print("Getting page")
    if manga_id < 1 or page_number < 1 or chapter_number < 1:
        # print("Too Low")
        return IMAGE_404()
    
    manga: Manga | None = db.Manga.fromID(id=manga_id)
    if manga is None:
        # print("Manga Not Real")
        return IMAGE_404()
    
    chapter: Chapter | None = db.Chapter.fromManga(manga=manga, number=chapter_number)
    if chapter is None:
        # print("Chapter Not Real")
        return IMAGE_404()
    
    page: Page | None = db.Page.fromChapter(chapter=chapter, number=page_number)
    if page is None:
        # print("Page Not Real")
        return IMAGE_404()
    
    # print(page)
    return FETCH_PAGE(page)

def fetch_page(page: Page):
    if page.chapter.is_archive():
        if page.chapter.archive_type == ".zip" or page.chapter.archive_type == ".cbz":
            # TODO Add try catch
            with zipfile.ZipFile(page.chapter.path, "r") as zip_file:
                image_data = zip_file.open(page.file_name)
                image_ext = os.path.splitext(page.file_name)[1]
                response = send_file(image_data, download_name=f"{page.number}{image_ext}", max_age=10*24*60*60)
                
            if response.status_code == 304:
                response.status_code = 200
            return response
        elif page.chapter.archive_type == ".pdf":
            pdf = pymupdf.open(page.chapter.path)
            base_image = pdf.extract_image(int(page.file_name))
            image_data = io.BytesIO(base_image["image"])
            image_ext = base_image["ext"]
            response = send_file(image_data, download_name=f"{page.number}{image_ext}", max_age=10*24*60*60)
                
            if response.status_code == 304:
                response.status_code = 200
            return response
        else:
            return IMAGE_404()
    else:
        img_path = os.path.join(page.chapter.path, page.file_name)
        # print(img_path, os.path.exists(img_path))
        if not os.path.exists(img_path):
            return IMAGE_404()
        
        ext = os.path.splitext(page.file_name)[1]
        response = send_from_directory(page.chapter.path, page.file_name, download_name=f"{page.number}{ext}", max_age=10*24*60*60)
        if response.status_code == 304:
            response.status_code = 200
        return response


@bp.route('/upload', methods=('GET', 'POST'))
def upload():
    pass

TERM_PATTERN = re.compile(r"(?<![:\",'])\b\w+\b(?![:\",'])")
TAG_PATTERN = re.compile(r"(?<!\w|!)tag:([\w,]+)")
NTAG_PATTERN = re.compile(r"!tag:([\w,]+)")
DQUOTE_PATTERN = re.compile(r"\"(.*?)\"")
QUOTE_PATTERN = re.compile(r"'(.*?)'")

UNREAD = "unread"
READ = "read"
TAGGED = "tagged"
UNTAGGED = "untagged"
IN_PROGRESS = "progress"
SFW = "sfw"
NSFW = "nsfw"

SPECIAL_TAGS = [READ, UNREAD, TAGGED, UNTAGGED, IN_PROGRESS, NSFW, SFW]


@bp.route("/search")
def search():
    q = request.args.get('q')
    if q is None:
        return render_template("manga/search.html", results=[])
    count = db.session.scalar(select(func.count()).select_from(api.create_search_query(q)))
    # print("COUNT:", count)
    
    return render_template("manga/search.html", COUNT=count, title="Results", HIDE_TITLES=HIDE_TITLES)

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