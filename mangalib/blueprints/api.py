import os

from flask import (
    Blueprint, flash, request
)

from . import settings
from .auth import owner_access
from .manga import registerMangaPath

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/scan-paths', methods=['POST'])
@owner_access
def scanPaths():
    paths = getPaths()['paths']
    print(f"Need to scan {len(paths)} paths")
    for path in paths:
        folders = lsDirs(path)['folders']
        print(f"Need to scan {len(folders)} folders")
        for folder in folders:
            registerMangaPath(path, folder)
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
                # flash("Path Added", 'success')
            else:
                error = 'Unable to add path'
        except:
            error = 'Error while adding path'
        
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

    dir = os.path.normpath(dir).replace('\\', '/')

    if dir == '/':
        return { 'dir': '/', 'folders': getRootFolders() }
    elif os.path.isdir(dir):
        if not dir.endswith(':/'):
            dir += '/'
        return { 'dir': dir, 'folders': [ path for path in os.listdir(dir) if isValidPath(dir, path) ] }
    else:
        return { 'dir': dir, 'folders': [] }
    
def lsFiles(dir: str | None):
    if not dir:
        return { 'dir': dir, 'files': [] }
    
    dir = os.path.normpath(dir).replace('\\', '/')
    if os.path.isfile(dir):
        return { 'dir': dir, 'files': [ dir ] }
    elif os.path.isdir(dir):
        return { 'dir': dir, 'files': [ file for file in os.listdir(dir) if isValidFile(dir, file) ] }
    
@bp.route('/is-dir')
@owner_access
def isDir():
    dir: str = request.args['dir']
    if dir is None:
        return { 'valid': False }
    return {'valid': os.path.isdir(dir)}

def getRootFolders():
    if os.name == 'nt':
        return [f'{drive}:/' for drive in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{drive}:/')]
    elif os.name == 'posix': 
        return os.listdir('/')
    else:
        return []
    
def isValidPath(dir: str, path: str):
    isDir = os.path.isdir(f'{dir}/{path}/')
    return isDir and not path.startswith('.') and not path.startswith('$')

def isValidFile(dir: str, file: str):
    isFile = os.path.isfile(f'{dir}/{file}')
    return isFile and not file.startswith('.') and not file.startswith('$')