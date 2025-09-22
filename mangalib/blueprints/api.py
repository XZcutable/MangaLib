import os

from flask import (
    Blueprint, flash, request, render_template, redirect, url_for, Response
)

from . import settings
from .auth import owner_access, admin_access
from . import manga as m
from .models import db, Manga, Chapter, Page, ContentTag

from . import models

import re

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/scan-paths', methods=['POST'])
@owner_access
def scanPaths():
    paths = getPaths()['paths']
    print(f"Need to scan {len(paths)} paths")
    found_manga: list = []
    for path in paths:
        folders = lsDirs(path)['folders']
        # print(f"Need to scan {len(folders)} folders")
        for folder in folders:
            manga = m.createManga(path, folder)
            found_manga.append(manga)
        #     break
        # break

    db.session.add_all(found_manga)
    db.session.commit()
    flash("Scanning", 'info')
    return {'result': 'success'}

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

@bp.route('/generate-manga-cards')
def generate_manga_cards():
    sort = request.args.get('sort', 'asc')
    offset = request.args.get('offset', 0)
    count = request.args.get('count', 30)

    titles = m.fetchTitles(sort=sort, offset=offset, count=count)

    html = render_template("manga/grid_generator.html", titles=titles, HIDE_TITLES=m.HIDE_TITLES)
    return html.lstrip()

@bp.route('/edit/manga/<int:manga_id>')
@admin_access
def edit_manga(manga_id: int):
    manga = Manga.fromID(manga_id)
    if manga is None:
        return redirect(url_for("home"))
    
    return render_template("manga/manga_editor.html", manga=manga.toJson())

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

valid_tag_regex = "^[a-z]+(\W+[a-z]*)*[a-z]$"
valid_tag_pattern = re.compile(valid_tag_regex)

@bp.route('/content-tag/add', methods=['POST'])
def add_content_tag():
    new_tag = request.form['content-tag'].lower()
    if valid_tag_pattern.fullmatch(new_tag):
        if ContentTag.query.where(ContentTag.tag == new_tag).one_or_none() is None:
            tag = ContentTag(tag=new_tag)
            db.session.add(tag)
            db.session.commit()
            flash("Added Tag", "success")
            return redirect(location=request.referrer)
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
    return { "tags": [ row.tag for row in ContentTag.query.values(ContentTag.tag) ] }

@bp.route('/content-tag/<int:manga_id>')
def get_manga_tags(manga_id: int):
    manga: Manga = Manga.fromID(manga_id)
    if manga is None:
        return Response(status=403)
    return { "tags": [ row.tag for row in manga.manga_metadata.tags ] }

@bp.route('/content-tag/set', methods=["POST"])
def set_content_tags():
    print(request.args)
    print(request.form)

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