from flask import (
    Flask, Blueprint, redirect, render_template, request, url_for, send_from_directory, send_file, g
)

from . import api
from .models import db, Manga, Chapter, Page, Path, UserMangaData, MangaMetadata, ContentTag, MangaContentTag
from .auth import get_role_context
from .constants import VAR, HTML, ROUTE, ENDPOINT

from sqlalchemy import func, select, text, bindparam, and_, or_, any_, not_, all_, distinct, join
from sqlalchemy import Select, Subquery

import os, re

image_types = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')

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
    return render_template(HTML.HOME, titles=random_titles, HIDE_TITLES=HIDE_TITLES)

def fetchTitles(sort: str = VAR.ASC, offset = 0, count = 30):
    query = select(Manga.id, Manga.title)
    if sort == VAR.ASC:
        query = query.order_by(Manga.id.asc())
    elif sort == VAR.DESC:
        query = query.order_by(Manga.id.desc())

    query = query.offset(offset)
    if count > 0:
        query = query.limit(min(count, 100))

    return [{ "id": result[0], "title": result[1] } for result in db.session.execute(query)]

@bp.route(ROUTE.LATEST)
def latest_titles():
    return render_template(HTML.INFINITE_SCROLL, sort=VAR.DESC, title="Latest", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.ALL)
def all_titles():
    return render_template(HTML.INFINITE_SCROLL, sort=VAR.ASC, title="All", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.HISTORY)
def history():
    return render_template(HTML.HISTORY, sort=VAR.DESC, title="History", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.FAVORITES)
def favorites():
    return render_template(HTML.FAVORITES, sort=VAR.DESC, title="Favorites", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.QUEUED)
def queued():
    return render_template(HTML.QUEUED, sort=VAR.DESC, title="To Read", HIDE_TITLES=HIDE_TITLES)

@bp.route(ROUTE.RANDOM)
def random_manga():
    random_id = db.session.scalar(select(Manga.id).order_by(func.random()))
    return redirect(f"{url_for(ENDPOINT.MANGA_RESUME, manga_id=random_id)}")

@bp.route(ROUTE.RANDOM_UNREAD)
def random_unread():
    user_id = api.getUserID()
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
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    
    user_manga_data: UserMangaData = UserMangaData.getOrCreate(api.getUserID(), manga)

    return render_template(HTML.INFO, manga=manga.toJson(), user_manga_data=user_manga_data.toJson(), HIDE_TITLES=HIDE_TITLES, **get_role_context())

@bp.route("/resume/<int:manga_id>")
@bp.route("/resume/<int:manga_id>/<int:chapter_number>")
def resume(manga_id: int, chapter_number: int=0):
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    progress: UserMangaData = UserMangaData.getOrCreate(g.user["id"], manga)

    progress_data = { "manga_id": manga.id, "page_number": progress.current_page, "chapter_number": progress.current_chapter }
    if chapter_number <= 0 and progress.new:
        progress_data = { "manga_id": manga.id, "page_number": 1, "chapter_number": 1 }
    elif chapter_number > 0 and (progress.new or chapter_number != progress.current_chapter):
        progress_data = { "manga_id": manga.id, "page_number": 1, "chapter_number": chapter_number }

    return redirect(url_for(ENDPOINT.MANGA_READ, **progress_data))

@bp.route('/<int:manga_id>/<int:page_number>')
@bp.route('/<int:manga_id>/<int:chapter_number>/<int:page_number>')
def read(manga_id: int, page_number=0, chapter_number=1):
    if page_number <= 0:
        return info(manga_id=manga_id)
    
    manga: Manga | None = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    
    chapter: Chapter | None = Chapter.fromManga(manga=manga, number=chapter_number)
    if chapter is None:
        return redirect(f"{url_for(ENDPOINT.MANGA_INFO, manga_id=manga_id)}")
    
    page: Page | None = Page.fromChapter(chapter, page_number)
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
    
    manga: Manga | None = Manga.fromID(id=manga_id)
    if manga is None:
        # print("Manga Not Real")
        return IMAGE_404()
    
    chapter: Chapter | None = Chapter.fromManga(manga=manga, number=chapter_number)
    if chapter is None:
        # print("Chapter Not Real")
        return IMAGE_404()
    
    page: Page | None = Page.fromChapter(chapter=chapter, number=page_number)
    if page is None:
        # print("Page Not Real")
        return IMAGE_404()
    
    # print(page)
    return FETCH_PAGE(page)

def fetch_page(page: Page):
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
    
    q = q.lower()
    terms: list[str] = [*TERM_PATTERN.findall(q), *[*DQUOTE_PATTERN.findall(q), *QUOTE_PATTERN.findall(q)]]
    tags: list[str] = TAG_PATTERN.findall(q)
    ntags: list[str] = NTAG_PATTERN.findall(q)

    manga_query = select(distinct(Manga.id), Manga.title)

    def is_special_tag(tag):
        return tag in SPECIAL_TAGS

    def handle_special_tag(tag, positive, metadata_query: Select[tuple[int]]):
        if tag == UNTAGGED:
            tag = TAGGED
            positive = not positive
        elif tag == SFW:
            tag = NSFW
            positive = not positive
        elif tag == UNREAD:
            tag = READ
            positive = not positive

        global user_id
        if tag == READ:
            user_id = api.getUserID()
            read_query = (
                select(Manga.id)
                .join(UserMangaData, (Manga.id == UserMangaData.manga_id) & (UserMangaData.user_id == user_id))
                .where(UserMangaData.is_read)
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(read_query))
            else:
                filter = filter.where(~Manga.id.in_(read_query))
            return filter
        elif tag == TAGGED:
            tag_query = (
                select(MangaContentTag.manga_id)
                .group_by(MangaContentTag.manga_id)
                .having(func.count() > 0)
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(tag_query))
            else:
                filter = filter.where(~Manga.id.in_(tag_query))
            return filter
        elif tag == IN_PROGRESS:
            user_id = api.getUserID()
            progress_query = (
                select(Manga.id)
                .join(UserMangaData, (Manga.id == UserMangaData.manga_id) & (UserMangaData.user_id == user_id))
                .where((~UserMangaData.is_read) & ((UserMangaData.current_chapter > 1) | (UserMangaData.current_page > 1)))
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(progress_query))
            else:
                filter = filter.where(~Manga.id.in_(progress_query))
            return filter
        elif tag == NSFW:
            tag_query = (
                select(MangaContentTag.manga_id)
                .group_by(MangaContentTag.manga_id)
                .join(ContentTag)
                .having(func.count(ContentTag.nsfw) > 0)
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(tag_query))
            else:
                filter = filter.where(~MangaContentTag.manga_id.in_(tag_query))
            return filter
        else:
            pass

    def replace_symbols(ls: list[str]):
        for i in range(len(ls)):
            ls[i] = ls[i].replace("_", " ")
            ls[i] = ls[i].strip(", ")

    def split_tags(tags: list[str], some: list[str], all: list[list[str]]):
        for tag in tags:
            if ',' in tag:
                all.append(tag.split(','))
            else:
                some.append(tag)
    
    replace_symbols(terms)
    replace_symbols(tags)
    replace_symbols(ntags)

    for term in terms:
        manga_query = manga_query.where(Manga.title.contains(term))

    if len(tags) or len(ntags):
        manga_query = manga_query.outerjoin(MangaContentTag, Manga.id == MangaContentTag.manga_id)

    if len(tags) > 0:
        or_tags:list[str] = []
        and_tags_list:list[list[str]] = []
        split_tags(tags, or_tags, and_tags_list)

        for or_tag in [tag for tag in or_tags]:
            if is_special_tag(or_tag):
                manga_query = handle_special_tag(or_tag, True, manga_query)
                or_tags.remove(or_tag)

        if len(or_tags):
            manga_query = manga_query.where(MangaContentTag.tag.in_(or_tags))

        for and_tags in and_tags_list:
            for and_tag in [tag for tag in and_tags]:
                if is_special_tag(and_tag):
                    and_tags.remove(and_tag)
                    manga_query = handle_special_tag(and_tag, True, manga_query)
            tag_query = (
                select(MangaContentTag.manga_id)
                .where(MangaContentTag.tag.in_(and_tags))
                .group_by(MangaContentTag.manga_id)
                .having(func.count() == len(and_tags))
            )
            manga_query = manga_query.where(Manga.id.in_(tag_query))

    if len(ntags) > 0:
        nor_tags:list[str] = []
        nand_tags_list:list[list[str]] = []
        split_tags(ntags, nor_tags, nand_tags_list)

        for nor_tag in [tag for tag in nor_tags]:
            if is_special_tag(nor_tag):
                manga_query = handle_special_tag(nor_tag, False, manga_query)
                nor_tags.remove(nor_tag)

        for nand_tags in nand_tags_list:
            for nand_tag in [tag for tag in nand_tags]:
                if is_special_tag(nand_tag):
                    # nand_tags.remove(nand_tag)
                    manga_query = handle_special_tag(nand_tags, False, manga_query)
                else:
                    nor_tags.append(nand_tag)

        if len(nor_tags):
            tag_query = (
                select(MangaContentTag.manga_id)
                .where(MangaContentTag.tag.in_(nor_tags))
                .group_by(MangaContentTag.manga_id)
                .having(func.count() > 0)
            )
            manga_query = manga_query.where(MangaContentTag.manga_id.not_in(tag_query)) # Shows Only Tagged
            # manga_query = manga_query.where(Manga.id.not_in(tag_query)) # Shows Untagged


    results = [{"id": id, "title": title} for (id, title) in db.session.execute(manga_query)]
    # print(results)
    # print(len(results))

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