import os

from flask import (
    Blueprint, flash, request, render_template, redirect, url_for, Response, g
)

from sqlalchemy import and_, select

from . import settings
from .auth import owner_access, admin_access, get_role_context
from .constants import ENDPOINT
from . import manga as m
from .models import db, Manga, Chapter, Page, ContentTag, UserMangaData, User, Path

import re
from datetime import datetime, timezone

bp = Blueprint('api', __name__, url_prefix='/api')

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

    print(f"Need to scan {len(paths)} paths")
    db.session.begin_nested()
    for path in paths:
        manga_folders = lsDirs(path)['folders']
        for manga_folder in manga_folders:
            manga_path = os.path.join(path, manga_folder)
            scan_manga_path(manga_path)
    
    db.session.commit()
    flash("Scanning", 'info')
    return {'result': 'success'}

@owner_access
@bp.route('/scan-manga')
def rescan():
    manga_id = request.args.get("manga_id")
    manga: Manga = db.session.get(Manga, {"id": manga_id})
    if manga is None:
        flash(f"Manga {manga_id} not found", "error")
    else:
        db.session.begin_nested()
        (success, error) = scan_manga_path(manga.path, manga)
        if success:
            flash("Rescanned Manga", "success")
            db.session.commit()
        else:
            flash(f"Unable to rescan manga: {error}", "error")
            db.session.rollback()
        
    return redirect(request.referrer)

def scan_manga_path(path: str, manga: Manga = None):
    if manga is not None and path != manga.path:
            print(f"Manga Path mismatch: got {path}, expected {manga.path}")
            return (False, f"Manga Path mismatch: got {path}, expected {manga.path}")
    else:
        manga_name = os.path.split(path)[1]
        manga = Manga.getOrCreate(title=manga_name, manga_path=path)
        manga.chapters = []

        chapter_names: list[str] = lsDirs(path)['folders']
        Path.sortList(chapter_names)
        chapter_names.insert(0, path)
        next_chapter_number = 1
        for chapter_name in chapter_names:
            chapter_path = os.path.join(path, chapter_name)
            page_names: list[str] = lsFiles(chapter_path, filters=m.image_types)['files']
            Path.sortList(page_names)

            if len(page_names) == 0:
                continue

            chapter: Chapter = Chapter.create(chapter_path=chapter_path, number=next_chapter_number, title=chapter_name)
            next_chapter_number += 1

            next_page_number = 1
            for page_name in page_names:
                page: Page = Page.create(file_name=page_name, number=next_page_number)
                next_page_number += 1
                chapter.pages.append(page)
            manga.chapters.append(chapter)
        
        if manga.new:
            manga.date_uploaded = getDatetimeISONow()
            db.session.add(manga)

        print(f"Manga ({manga.id}, {manga.title}), updated with {len(manga.chapters)} chapter(s)")
        return (True, None)

@bp.route('/add-path')
@owner_access
def addPath():
    path: str = request.args['path']
    error = None
    result = { 'success': False }

    if path is None:
        error = "No path given"
    else: 
        try:
            path = os.path.normpath(path).replace('\\', '/')
        
            if not os.path.isdir(path):
                error = "Path is not a dir"
            elif path in settings.getPaths():
                error = "Path is already registered"
            elif settings.addPath(path):
                result = { 'success': True }
                flash("Path Added", 'success')
            else:
                error = 'Unable to add path'
        except Exception as e:
            error = f'Error while adding path: {e}'
        
    if error is not None:
        flash(error, 'error')

    return result

@bp.route('/remove-path')
@owner_access
def removePath():
    path: str = request.args['path']
    error = None
    result = { 'success': False }

    try:
        path = os.path.normpath(path).replace('\\', '/')
    
        if settings.removePath(path):
            result = { 'success': True }
            # flash("Path Removed", 'success')
        else:
            error = 'Unable to remove path'
    except:
        error = 'Error while removing path'

    if error is not None:
        flash(error, 'error')
    return result

@bp.route('/get-paths')
@owner_access
def getPaths():
    return {
        'paths': settings.getPaths()
    }
    
@bp.route('/list-dir')
@owner_access
def listDirs():
    dir: str = request.args['dir']
    return lsDirs(dir)
    
def lsDirs(dir: str | None):
    if not dir:
        return { 'dir': dir, 'folders': [] }
    
    if dir.endswith(':/..'):
        dir = '/'

    if dir.startswith('/'):
        dir = ('/' + os.path.normpath(dir).replace('\\', '/')).replace('//', '/')
    else:
        dir = os.path.normpath(dir).replace('\\', '/')

    if dir == '/':
        (dir, folder) = getRootFolders()
        return { 'dir': dir, 'folders':  folder}
    elif os.path.isdir(dir):
        if not dir.endswith(':/'):
            dir += '/'
        return { 'dir': dir, 'folders': [ path for path in os.listdir(dir) if isValidPath(dir, path) ] }
    else:
        return { 'dir': dir, 'folders': [] }
    
def lsFiles(dir: str | None, filters: tuple | None):
    if not dir:
        return { 'dir': dir, 'files': [] }
    
    dir = os.path.normpath(dir).replace('\\', '/')
    if os.path.isfile(dir):
        if filters is None or os.path.splitext(dir)[1] in filters:
            return { 'dir': dir, 'files': [ dir ] }
        else:
            return { 'dir': dir, 'files': [] }
            
    elif os.path.isdir(dir):
        return { 'dir': dir, 'files': [ file for file in os.listdir(dir) if isValidFile(dir, file, filters) ] }
    
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
        manga = Manga.fromID(manga_id)
        if manga is not None:
            db.session.delete(manga)
            db.session.commit()
            return redirect(url_for(ENDPOINT.HOME))

    return redirect(url_for(ENDPOINT.HOME))

def getRootFolders():
    if os.name == 'nt':
        folders = [f'{drive}:/' for drive in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{drive}:/')]
        return ('', folders)
    elif os.name == 'posix': 
        folders = os.listdir('/')
        return ('/', folders)
    else:
        return []
    
def isValidPath(dir: str, path: str):
    isDir = os.path.isdir(f'{dir}/{path}/')
    return isDir and not path.startswith('.') and not path.startswith('$')

def isValidFile(dir: str, file: str, filters: tuple | None):
    if os.path.isfile(f'{dir}/{file}'):
        if not file.startswith('.') and not file.startswith('$'):
            if filters is None:
                return True
            else:
                return os.path.splitext(file)[1] in filters
    
    return False

@bp.route('/fetch-titles')
def fetch_titles():
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))
    count = int(request.args.get('count', '30'))

    titles = m.fetchTitles(sort=sort, offset=offset, count=count)
    return titles

@bp.route("/fetch-history")
def fetch_history():
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))
    count = int(request.args.get('count', '30'))

    query = select(Manga.id, Manga.title)
    user_id = getUserID()
    #, UserMangaData.last_seen != None
    query = query.join_from(Manga, UserMangaData, and_(Manga.id == UserMangaData.manga_id, UserMangaData.user_id == user_id))
    if sort == 'asc':
        query = query.order_by(UserMangaData.last_seen.asc().nulls_last())
    elif sort == 'desc':
        query = query.order_by(UserMangaData.last_seen.desc().nulls_last())
    
    query = query.offset(offset).limit(min(count, 100))

    results = [{ "id": result[0], "title": result[1] } for result in db.session.execute(query)]
    # print(results)
    return results

@bp.route("/fetch-favorites")
def fetch_favorites():
    sort = request.args.get('sort', 'asc')
    offset = int(request.args.get('offset', '0'))
    count = int(request.args.get('count', '30'))

    query = select(Manga.id, Manga.title)
    user_id = getUserID()
    #, UserMangaData.last_seen != None
    query = query.join_from(Manga, UserMangaData, and_(Manga.id == UserMangaData.manga_id, UserMangaData.user_id == user_id, UserMangaData.is_favorite))
    if sort == 'asc':
        query = query.order_by(UserMangaData.favorited_when.asc().nulls_last())
    elif sort == 'desc':
        query = query.order_by(UserMangaData.favorited_when.desc().nulls_last())
    
    query = query.offset(offset).limit(min(count, 100))

    results = [{ "id": result[0], "title": result[1] } for result in db.session.execute(query)]
    # print(results)
    return results

@bp.route('/edit/manga/<int:manga_id>')
@admin_access
def edit_manga(manga_id: int):
    manga: Manga = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for(ENDPOINT.HOME))
    return render_template("manga/manga_editor.html", manga=manga.toJson(), **get_role_context())

@bp.route('/settings/config', methods=['GET','POST'])
@owner_access
def edit_config():
    if request.method == 'POST':
        if request.form.get("hide-manga"):
            m.hide_content(request.form["hide-manga"].lower() != 'false')
        
        if request.form.get("hide-titles"):
            m.hide_titles(request.form["hide-titles"].lower() != 'false')
        return Response(status=200)
    else:
        return {
            "hide-manga": m.HIDE_MANGA,
            "hide-titles": m.HIDE_TITLES
        }
    
@bp.route("/edit/manga/title/<int:manga_id>", methods=["POST"])
@admin_access
def edit_manga_title(manga_id: int):
    manga: Manga = Manga.fromID(manga_id)
    if manga is not None:
        if request.form.get('title') is not None:
            manga.title = request.form['title']
            db.session.commit()
            return Response(status=200)
    return Response(status=403)

@bp.route("/manga/info/<int:manga_id>")
def get_manga_info(manga_id: int):
    manga: Manga = Manga.fromID(manga_id)
    if manga is None:
        return {}
    else:
        return manga.toJson()
    
@bp.route("/chapter/info/<int:manga_id>/<int:chapter_number>")
def get_chapter_info(manga_id: int, chapter_number):
    manga: Manga = Manga.fromID(manga_id)
    if manga is None:
        return {}
    else:
        chapter: Chapter = Chapter.fromManga(manga, chapter_number)
        if chapter is None:
            return {}
        else:
            return chapter.toJson()
        
@bp.route("/chapter/info/<int:manga_id>/<int:chapter_number>/<int:page_number>")
def get_page_info(manga_id: int, chapter_number: int, page_number: int):
    manga: Manga = Manga.fromID(manga_id)
    if manga is None:
        return {}
    else:
        chapter: Chapter = Chapter.fromManga(manga, chapter_number)
        if chapter is None:
            return {}
        else:
            page: Page = Page.fromChapter(chapter, page_number)
            if page is None:
                return {}
            else:
                return page.toJson()

valid_tag_regex = r"^[a-z]+(\W+[a-z]*)*[a-z]$"
valid_tag_pattern = re.compile(valid_tag_regex)

@bp.route('/content-tag/add', methods=['POST'])
def add_content_tag():
    new_tag = request.form['content-tag'].lower()
    if valid_tag_pattern.fullmatch(new_tag):
        existing_tag: ContentTag = ContentTag.query.where(ContentTag.tag == new_tag).one_or_none()
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
def add_nsfw_tag():
    new_tag = request.form['content-tag'].lower()
    if valid_tag_pattern.fullmatch(new_tag):
        existing_tag: ContentTag = ContentTag.query.where(ContentTag.tag == new_tag).one_or_none()
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
def remove_content_tag():
    remove_tag = request.form['content-tag'].lower()
    if valid_tag_pattern.fullmatch(remove_tag):
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
    manga: Manga = Manga.fromID(manga_id)
    if manga is None:
        return Response(status=403)
    
    tags = [ row.tag for row in manga.manga_metadata.tags ]
    tags.sort()
    return { "tags": tags }

@bp.route('/content-tag/set', methods=["POST"])
def set_content_tags():
    manga: Manga = Manga.fromID(request.args.get("manga_id", 0))
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

@bp.route('/user/manga/data')
def get_user_manga_data():
    manga: Manga = Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        user_data: UserMangaData = UserMangaData.getOrCreate(getUserID(), manga)
        return user_data.toJson()
    return Response(status=405)

@bp.route('/user/manga/progress', methods=["POST"])
def save_user_progress():
    manga: Manga = Manga.fromID(request.form.get("manga_id", 0))
    if manga is not None:
        chapter: Chapter = Chapter.fromManga(manga, request.form.get("chapter_number", 0))
        if chapter is not None:
            page: Page = Page.fromChapter(chapter, request.form.get("page_number", 0))
            if page is not None:
                user_data: UserMangaData = UserMangaData.getOrCreate(getUserID(), manga)
                if user_data.new:
                    db.session.add(user_data)

                user_data.current_chapter = chapter.number
                user_data.current_page = page.number
                user_data.last_seen = getDatetimeISONow()

                if chapter.number >= len(manga.chapters) and page.number >= len(chapter.pages):
                    user_data.is_read = True
                    user_data.current_page = 1

                db.session.commit()
                return Response(status=200)
    return Response(status=405)
    
@bp.route('/user/manga/read', methods=["POST"])
def update_read_status():
    manga: Manga = Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        user_data: UserMangaData = UserMangaData.getOrCreate(getUserID(), manga)
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
    manga: Manga = Manga.fromID(request.args.get("manga_id", 0))
    if manga is not None:
        user_data: UserMangaData = UserMangaData.getOrCreate(getUserID(), manga)
        is_fav = request.form.get("is_fav", 'False').lower() == "true"
        db.session.begin_nested()
        if user_data.new:
            db.session.add(user_data)
        if is_fav != user_data.is_favorite:
            user_data.is_favorite = is_fav
        user_data.favorited_when = getDatetimeISONow()
        db.session.commit()
        return user_data.toJson()

    return Response(status=405)

def getCurrentUser() -> User:
    return g.user

def getUserID() -> int:
    return getCurrentUser()["id"]

# Seems like Jinja datetime doesn't preserve the timezone when converting to a string so just skipping the middle man
def getDatetimeISONow():
    return str(datetime.now(timezone.utc))

def fromDatetimeISO(iso:str):
    return datetime.fromisoformat(iso)