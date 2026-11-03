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

from ..server import api, settings, library

from ..quries import QUERY_FAVORITES, QUERY_HISTORY, QUERY_QUEUE
from ..server.search import create_search_query

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

    api.scan_library(paths)
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
    return _fetch_list("all")

@bp.route("/fetch-history")
def fetch_history():
    return _fetch_list("history")

@bp.route("/fetch-favorites")
def fetch_favorites():
    return _fetch_list("favorites")

@bp.route("/fetch-queued")
def fetch_queued():
    return _fetch_list("queued")

def _fetch_list(list_name: str):
    # The Jinja pages pass sort themselves and expect "asc" when they don't
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))
    query = library.list_query(list_name, db.session.getUserID(), sort)
    return library.fetch(query, offset, FETCH_BATCH_SIZE)

@bp.route("fetch-search")
def fetch_search():
    sort = request.args.get('sort', "asc")
    offset = int(request.args.get('offset', 0))
    q = request.args.get("q")
    
    if q is None:
        return []
    
    return library.fetch(library.search_query(q, sort), offset, FETCH_BATCH_SIZE)

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
        user_data = library.save_progress(db.session.getUserID(), manga, request.form.get("chapter_number", 0), request.form.get("page_number", 0))
        if user_data is not None:
            return Response(status=200)
    return Response(status=405)
    
@bp.route('/user/manga/read', methods=["POST"])
def update_read_status():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        is_read = request.form.get("is_read", 'False').lower() == "true"
        reset = request.form.get("reset", 'False').lower() == "true"
        return library.update_state(db.session.getUserID(), manga, is_read=is_read, reset=reset).toJson()

    return Response(status=405)

@bp.route('/user/manga/favorite', methods=["POST"])
def update_fav_status():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        is_fav = request.form.get("is_fav", 'False').lower() == "true"
        return library.update_state(db.session.getUserID(), manga, is_favorite=is_fav).toJson()

    return Response(status=405)

@bp.route('/user/manga/queue', methods=["POST"])
def update_queue_status():
    manga: Manga = db.Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        is_queued = request.form.get("is_queued", 'False').lower() == "true"
        return library.update_state(db.session.getUserID(), manga, is_queued=is_queued).toJson()

    return Response(status=405)
