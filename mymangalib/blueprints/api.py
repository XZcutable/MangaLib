import os, re
from datetime import datetime, timezone

from flask import (
    Flask, Blueprint, flash, request, render_template, redirect, url_for, Response, g
)

from sqlalchemy import and_, select

from ..auth import owner_access, admin_access, get_role_context
from ..constants import ENDPOINT, SQL
from . import manga
from sqlalchemy import distinct, func, Select

from ..database import db
from ..models import Manga, Chapter, Page, ContentTag, UserMangaData, User, Path, MangaContentTag

bp = Blueprint('api', __name__, url_prefix='/api')

from ..server import api, settings

from ..quries import QUERY_FAVORITES, QUERY_HISTORY, QUERY_QUEUE

FETCH_BATCH_SIZE = 30

def init_app(app: Flask):
    global FETCH_BATCH_SIZE
    FETCH_BATCH_SIZE = app.config.get("FETCH_BATCH_SIZE", FETCH_BATCH_SIZE)

@bp.route('/scan-paths', methods=['POST'])
@owner_access
def scanPaths():
    paths = getPaths()['paths']
    paths_to_scan = request.form.get("paths")
    if paths_to_scan is not None:
        if type(paths_to_scan) == str:
            if paths_to_scan in paths:
                paths = [paths_to_scan]
            else:
                flash(f"Path does not exist: {paths_to_scan}", 'error')
                return {'result': 'fail'}
        if type(paths_to_scan) == list[str]:
            actual_paths_to_scan = []
            for path in paths:
                if path in paths_to_scan:
                    actual_paths_to_scan.append(path)
                else:
                     flash(f"Path does not exist: {path}", 'error')
            if len(actual_paths_to_scan) == 0:
                flash(f"Found no paths to scan", 'error')
                return {'result': 'fail'}
            else:
                paths = actual_paths_to_scan

    # print(f"Need to scan {len(paths)} paths")
    db.session.begin_nested()
    for path in paths:
        new_manga: list[Manga] = api.scan_manga_path(path, rescan_exisitng=False)
        db.session.add_all(new_manga)
    
    db.session.commit()
    db.Manga.update_manga_count()
    flash("Path scanned", 'success')
    return {'result': 'success'}

@bp.route('/scan-manga')
@owner_access
def rescan():
    manga_id = request.args.get("manga_id")
    manga: Manga = db.Manga.fromID(manga_id)
    if manga is None:
        flash(f"Manga {manga_id} not found", "error")
    else:
        db.session.begin_nested()
        (success, error) = api.rescan_manga(manga)
        if success:
            flash("Rescanned Manga", "success")
            db.session.commit()
        else:
            flash(f"Unable to rescan manga: {error}", "error")
            db.session.rollback()
        
    return redirect(request.referrer)

@bp.route('/add-path')
@owner_access
def addPath():
    path: str = request.args['path']
    result = { 'success': False }

    path = os.path.normpath(path).replace('\\', '/')

    try:
        settings.add_path(path)
        result = { 'success': True }
        flash("Path Added", 'success')
    except ValueError as error:
        flash(error, 'error')
        
    return result

@bp.route('/remove-path')
@owner_access
def removePath():
    path: str = request.args['path']
    result = { 'success': False }
    path = os.path.normpath(path).replace('\\', '/')

    try:
        settings.remove_path(path)
        result = { 'success': True }
        flash("Path Removed", 'success')
    except ValueError as error:
        flash(error, 'error')

    return result

@bp.route('/get-paths')
@owner_access
def getPaths():
    return {
        'paths': settings.get_paths()
    }
    
@bp.route('/list-dir')
@owner_access
def listDirs():
    dir: str = request.args['dir']
    if not dir.endswith("/"):
        dir += "/"
    return {"dir": dir, "folders": api.lsDirs(dir)}
    
@bp.route('/open-dir/<int:manga_id>')
@owner_access
def open_manga_dir(manga_id: int):
    # print(manga_id)
    manga: Manga = db.session.get(Manga, {"id": manga_id})
    if manga is None:
        return {}
    else:
        return {"path": f"{manga.path}"}

@bp.route('/is-dir')
@owner_access
def isDir():
    dir: str = request.args['dir']
    if dir is None:
        return { 'valid': False }
    return {'valid': os.path.isdir(dir)}

@bp.route("/delete-manga")
@owner_access
def delete_manga():
    manga_id = request.args.get("manga_id")
    if manga_id is not None:
        manga = db.Manga.fromID(manga_id)
        if manga is not None:
            db.session.delete(manga)
            db.session.commit()
            db.Manga.update_manga_count()
            return redirect(url_for(ENDPOINT.HOME))

    return redirect(url_for(ENDPOINT.HOME))
    
@bp.route('/fetch-titles')
def fetch_titles():
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))

    query = (
        select(Manga.id, Manga.title)
        .order_by(SQL.ORDER.get(sort, SQL.ASC)(Manga.id))
        .offset(offset).limit(FETCH_BATCH_SIZE)
    )
    
    return db.session.execute_query(query, mappings=["id", "title"])

@bp.route("/fetch-history")
def fetch_history():
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))

    user_id = db.session.getUserID()
    query = (
        QUERY_HISTORY(user_id, sort)
        .offset(offset).limit(FETCH_BATCH_SIZE)
    )
    return db.session.execute_query(query, mappings=["id", "title"])

@bp.route("/fetch-favorites")
def fetch_favorites():
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))

    user_id = db.session.getUserID()
    query = (
        QUERY_FAVORITES(user_id, sort)
        .offset(offset).limit(FETCH_BATCH_SIZE)
    )

    return db.session.execute_query(query, mappings=["id", "title"])

@bp.route("/fetch-queued")
def fetch_queued():
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))

    user_id = db.session.getUserID()
    query = QUERY_QUEUE(user_id, sort)
    return db.session.execute_query(query.offset(offset).limit(FETCH_BATCH_SIZE), mappings=["id", "title"])

CACHE_LIMIT = 30
CACHE_LIFESPAN_SECONDS = 300
SEARCH_CACHE: dict[str, Select[tuple[int, str]]] = {}
CACHE_TIMESTAMPS: dict[str, datetime] = {}
@bp.route("fetch-search")
def fetch_search(q: str=None):
    sort = request.args.get('sort', "asc")
    offset = int(request.args.get('offset', 0))
    q = request.args.get("q")
    
    if q is None:
        return []
    
    query = (
        select(create_search_query(q).subquery().alias("manga"))
        .order_by(SQL.ORDER.get(sort, SQL.ASC)(Manga.id))
        .offset(offset).limit(FETCH_BATCH_SIZE)
    )
    print(query)
    return db.session.execute_query(query, mappings=["id", "title"])
    
def create_search_query(q: str):
    query = SEARCH_CACHE.get(q)
    if query is not None:
        CACHE_TIMESTAMPS[q] = datetime.now()
    else:
        query = create_search_query(q)
        oldest_key = None
        if len(CACHE_TIMESTAMPS.keys()) >= CACHE_LIMIT:
            now = datetime.now()
            oldest_age = None
            for key in CACHE_TIMESTAMPS.keys():
                age = (now-CACHE_TIMESTAMPS[key]).total_seconds()
                if age > CACHE_LIFESPAN_SECONDS:
                    CACHE_TIMESTAMPS.pop(key)
                    SEARCH_CACHE.pop(key)
                elif oldest_key is None:
                    oldest_key = key
                    oldest_age = age
                elif age > oldest_age:
                    oldest_key = key

        if len(CACHE_TIMESTAMPS.keys()) >= CACHE_LIMIT and oldest_key is not None:
            SEARCH_CACHE.pop(oldest_key)
            CACHE_TIMESTAMPS.pop(oldest_key)

        SEARCH_CACHE[q] = query
        CACHE_TIMESTAMPS[q] = datetime.now()

   

    return query

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

# TODO Move this to server and fix. also support partial search terms
def create_search_query(q: str) -> Select[tuple[int, str]]:
    q = q.lower()
    terms: list[str] = [*TERM_PATTERN.findall(q), *[*DQUOTE_PATTERN.findall(q), *QUOTE_PATTERN.findall(q)]]
    tags: list[str] = TAG_PATTERN.findall(q)
    ntags: list[str] = NTAG_PATTERN.findall(q)

    manga_query = select(Manga.id.label("id"), Manga.title).distinct()

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
            user_id = db.session.getUserID()
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
            user_id = db.session.getUserID()
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
            nsfw_query = (
                select(MangaContentTag.manga_id)
                .join(ContentTag, ContentTag.tag == MangaContentTag.tag)
                .where(ContentTag.nsfw)
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(nsfw_query))
            else:
                filter = filter.where(~Manga.id.in_(nsfw_query))
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
            if len(and_tags):
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
                    manga_query = handle_special_tag(nand_tag, False, manga_query)
                else:
                    nor_tags.append(nand_tag)

        if len(nor_tags):
            tag_query = (
                select(MangaContentTag.manga_id)
                .where(MangaContentTag.tag.in_(nor_tags))
                .group_by(MangaContentTag.manga_id)
                .having(func.count() > 0)
            )
            manga_query = manga_query.where(Manga.id.not_in(tag_query))

    return manga_query

@bp.route('/edit/manga/<int:manga_id>')
@admin_access
def edit_manga(manga_id: int):
    manga: Manga = db.Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    return render_template("manga/manga_editor.html", manga=manga.toJson(), **get_role_context())

@bp.route('/settings/config', methods=['GET','POST'])
@owner_access
def edit_config():
    if request.method == 'POST':
        if request.form.get("hide-manga"):
            manga.hide_content(request.form["hide-manga"].lower() != 'false')
        
        if request.form.get("hide-titles"):
            manga.hide_titles(request.form["hide-titles"].lower() != 'false')
        return Response(status=200)
    else:
        return {
            "hide-manga": manga.HIDE_MANGA,
            "hide-titles": manga.HIDE_TITLES
        }
    
@bp.route("/edit/manga/title/<int:manga_id>", methods=["POST"])
@admin_access
def edit_manga_title(manga_id: int):
    manga: Manga = db.Manga.fromID(manga_id)
    if manga is not None:
        if request.form.get('title') is not None:
            manga.title = request.form['title']
            db.session.commit()
            return Response(status=200)
    return Response(status=403)

# TODO Remove these? are we using this. Maybe the manga could stay
@bp.route("/manga/info/<int:manga_id>")
def get_manga_info(manga_id: int):
    manga: Manga = db.Manga.fromID(manga_id)
    if manga is None:
        return {}
    else:
        return manga.toJson()
    
@bp.route("/chapter/info/<int:manga_id>/<int:chapter_number>")
def get_chapter_info(manga_id: int, chapter_number):
    manga: Manga = db.Manga.fromID(manga_id)
    if manga is None:
        return {}
    else:
        chapter: Chapter = db.Chapter.fromManga(manga, chapter_number)
        if chapter is None:
            return {}
        else:
            return chapter.toJson()
        
@bp.route("/chapter/info/<int:manga_id>/<int:chapter_number>/<int:page_number>")
def get_page_info(manga_id: int, chapter_number: int, page_number: int):
    manga: Manga = db.Manga.fromID(manga_id)
    if manga is None:
        return {}
    else:
        chapter: Chapter = db.Chapter.fromManga(manga, chapter_number)
        if chapter is None:
            return {}
        else:
            page: Page = db.Page.fromChapter(chapter, page_number)
            if page is None:
                return {}
            else:
                return page.toJson()

# Lowercase words separated by single spaces, e.g. "slice of life"
valid_tag_regex = r"^[a-z]+( [a-z]+)*$"
valid_tag_pattern = re.compile(valid_tag_regex)

#TODO Move logic to server but keep api
@bp.route('/content-tag/add', methods=['POST'])
@admin_access
def add_content_tag():
    new_tag = request.form['content-tag'].lower()
    if valid_tag_pattern.fullmatch(new_tag):
        existing_tag: ContentTag = ContentTag.query.where(ContentTag.tag == new_tag).one_or_none() #TODO Update
        if existing_tag is None:
            tag = ContentTag(tag=new_tag)
            db.session.add(tag)
            db.session.commit()
            flash("Added Tag", "success")
        elif existing_tag.nsfw:
            existing_tag.nsfw = False
            db.session.commit()
            flash(f"Tag '{new_tag}' changed to SFW", "success")
        else:
            flash(f"Tag '{new_tag}' already exists", "error")

        return redirect(location=request.referrer)
    else:
        flash("Invalid Tag", "error")
        return redirect(location=request.referrer)
    
@bp.route('/content-tag/add-nsfw', methods=['POST'])
@admin_access
def add_nsfw_tag():
    new_tag = request.form['content-tag'].lower()
    if valid_tag_pattern.fullmatch(new_tag):
        existing_tag: ContentTag = ContentTag.query.where(ContentTag.tag == new_tag).one_or_none() # TODO Update
        if existing_tag is None:
            tag = ContentTag(tag=new_tag, nsfw=True)
            db.session.add(tag)
            db.session.commit()
            flash("Added Tag", "success")
        elif not existing_tag.nsfw:
            existing_tag.nsfw = True
            db.session.commit()
            flash(f"Tag '{new_tag}' changed to NSFW", "success")
        else:
            flash(f"Tag '{new_tag}' already exists", "error")
            
        return redirect(location=request.referrer)
    else:
        flash("Invalid Tag", "error")
        return redirect(location=request.referrer)
    
@bp.route('/content-tag/remove', methods=['POST'])
@admin_access
def remove_content_tag():
    remove_tag = request.form['content-tag'].lower()
    if remove_tag:
        tag = ContentTag.query.where(ContentTag.tag == remove_tag).one_or_none()
        if tag is not None:
            db.session.delete(tag)
            db.session.commit()
        flash("Removed Tag", "success")
        return redirect(location=request.referrer)
    else:
        flash("Invalid Tag", "error")
        return redirect(location=request.referrer)
    
@bp.route('/content-tag')
def get_content_tags():
    return { "tags": [ row.toJson() for row in ContentTag.query.order_by(ContentTag.tag).all() ] }

@bp.route('/content-tag/<int:manga_id>')
def get_manga_tags(manga_id: int):
    manga: Manga = db.Manga.fromID(manga_id)
    if manga is None:
        return Response(status=403)
    
    tags = [ row.tag for row in manga.manga_metadata.tags ]
    tags.sort()
    return { "tags": tags }

@bp.route('/content-tag/set', methods=["POST"])
@admin_access
def set_content_tags():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        metadata = manga.manga_metadata
        db.session.begin_nested()
        metadata.tags.clear()
        for tag in request.form.keys():
            content_tag: ContentTag = ContentTag.query.get({"tag": tag})
            if content_tag is not None:
                metadata.tags.append(content_tag)
        db.session.commit()

    return redirect(location=request.referrer)

#TODO Move logic to server
@bp.route('/user/manga/data')
def get_user_manga_data():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        user_data: UserMangaData = db.UserMangaData.getOrCreate(db.session.getUserID(), manga)
        return user_data.toJson()
    return Response(status=405)

@bp.route('/user/manga/progress', methods=["POST"])
def save_user_progress():
    manga: Manga = db.Manga.fromID(request.form.get("manga_id", 0))
    if manga is not None:
        chapter: Chapter = db.Chapter.fromManga(manga, request.form.get("chapter_number", 0))
        if chapter is not None:
            page: Page = db.Page.fromChapter(chapter, request.form.get("page_number", 0))
            if page is not None:
                user_data: UserMangaData = db.UserMangaData.getOrCreate(db.session.getUserID(), manga)
                if user_data.new:
                    db.session.add(user_data)

                user_data.current_chapter = chapter.number
                user_data.current_page = page.number
                user_data.last_seen = db.getDatetimeISONow()

                if chapter.number >= len(manga.chapters) and page.number >= len(chapter.pages):
                    user_data.is_read = True
                    user_data.is_queued = False
                    user_data.current_page = 1

                db.session.commit()
                return Response(status=200)
    return Response(status=405)
    
@bp.route('/user/manga/read', methods=["POST"])
def update_read_status():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        user_data: UserMangaData = db.UserMangaData.getOrCreate(db.session.getUserID(), manga)
        is_read = request.form.get("is_read", 'False').lower() == "true"
        reset = request.form.get("reset", 'False').lower() == "true"
        db.session.begin_nested()
        if user_data.new:
            db.session.add(user_data)
        if is_read != user_data.is_read:
            user_data.is_read = is_read
        if reset:
            user_data.current_chapter = 1
            user_data.current_page = 1
        db.session.commit()
        return user_data.toJson()

    return Response(status=405)

@bp.route('/user/manga/favorite', methods=["POST"])
def update_fav_status():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        user_data: UserMangaData = db.UserMangaData.getOrCreate(db.session.getUserID(), manga)
        is_fav = request.form.get("is_fav", 'False').lower() == "true"
        db.session.begin_nested()
        if user_data.new:
            db.session.add(user_data)
        user_data.is_favorite = is_fav
        if is_fav:
            user_data.favorited_when = db.getDatetimeISONow()
        else:
            user_data.favorited_when = ""
        db.session.commit()
        return user_data.toJson()

    return Response(status=405)

@bp.route('/user/manga/queue', methods=["POST"])
def update_queue_status():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        user_data: UserMangaData = db.UserMangaData.getOrCreate(db.session.getUserID(), manga)
        is_queued = request.form.get("is_queued", 'False').lower() == "true"
        db.session.begin_nested()
        if user_data.new:
            db.session.add(user_data)
        user_data.is_queued = is_queued
        if is_queued:
            user_data.queued_when = db.getDatetimeISONow()
        else:
            user_data.queued_when = ""
        db.session.commit()
        return user_data.toJson()

    return Response(status=405)

