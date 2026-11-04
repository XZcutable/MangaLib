from ..server.settings import has_path, add_path, get_paths, update_paths


from ..database import db, SUPPORTED_IMAGE_TYPES, SUPPORTED_ARCHIVE_TYPES
from ..models import Manga, Chapter, Page

from datetime import datetime, timezone
import os
from ..helpers import sort_paths, release_year_from_names



# Seems like Jinja datetime doesn't preserve the timezone when converting to a string so just skipping the middle man
def getDatetimeISONow():
    return str(datetime.now(timezone.utc))

def isValidPath(dir: str, path: str):
    isDir = os.path.isdir(f'{dir}/{path}/')
    return isDir and not path.startswith('.') and not path.startswith('$')

def isValidFile(dir: str, file: str, filters: tuple | None):
    if os.path.isfile(f'{dir}/{file}'):
        if not file.startswith('.') and not file.startswith('$'):
            if filters is None:
                return True
            else:
                return os.path.splitext(file)[1].lower() in filters
    
    return False

def getRootFolders():
    if os.name == 'nt':
        folders = [f'{drive}:/' for drive in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{drive}:/')]
        return folders
    elif os.name == 'posix': 
        folders = os.listdir('/')
        return folders
    else:
        return []

def lsDirs(dir: str | None):
    if not dir:
        return []
    
    if dir.endswith(':/..'):
        dir = '/'

    if dir.startswith('/'):
        dir = ('/' + os.path.normpath(dir).replace('\\', '/')).replace('//', '/')
    else:
        dir = os.path.normpath(dir).replace('\\', '/')

    if dir == '/':
        return getRootFolders()
    elif os.path.isdir(dir):
        if not dir.endswith(':/'):
            dir += '/'
        return [ path for path in os.listdir(dir) if isValidPath(dir, path) ]
    else:
        return []

def lsFiles(dir: str | None, filters: tuple | None):
    if not dir:
        return []
    
    dir = os.path.normpath(dir).replace('\\', '/')
    if os.path.isfile(dir):
        if filters is None or os.path.splitext(dir)[1].lower() in filters:
            return [ dir ]
        else:
            return []
            
    elif os.path.isdir(dir):
        return [ file for file in os.listdir(dir) if isValidFile(dir, file, filters) ]

def scan_archive_as_manga(archive_path: str, archive_name: str, rescan_exisitng: bool = False):
    archive_name, archive_ext = os.path.splitext(archive_name)
    archive_ext = archive_ext.lower()

    manga: Manga = db.Manga.getOrCreate(title=archive_name, manga_path=archive_path)
    if not manga.new and not rescan_exisitng:
        # print("Skipping:", archive_path)
        return None
    
    # print("Scanning:", archive_path)

    manga.chapters = []
    
    chapter: Chapter = db.Chapter.create(chapter_path=archive_path, number=1, title=archive_name, archive_type=archive_ext)
    db.Chapter.from_archive(chapter, archive_path=archive_path, archive_ext=archive_ext)

    if len(chapter.pages) <= 0:
        return None
    else:
        manga.chapters.append(chapter)

    manga.release_year = release_year_from_names([archive_name])
    if manga.new:
        manga.last_updated = manga.date_uploaded
    return manga

def count_chapter_entries(manga_path: str) -> int:
    """Chapter folders and archives in a manga folder, plus 1 for images loose in the folder itself."""
    entries = len(lsDirs(manga_path)) + len(lsFiles(manga_path, filters=SUPPORTED_ARCHIVE_TYPES) or [])
    if lsFiles(manga_path, filters=SUPPORTED_IMAGE_TYPES):
        entries += 1
    return entries

def scan_manga(manga_path: str, manga_name: str, rescan_exisitng: bool = False):
    manga: Manga = db.Manga.getOrCreate(title=manga_name, manga_path=manga_path)

    if manga.new:
        manga.date_uploaded = db.getDatetimeISONow()
    elif not rescan_exisitng and count_chapter_entries(manga_path) <= len(manga.chapters):
        # Nothing new on disk. Empty chapter folders are never added, so an equal or lower count means no new content.
        return None

    previous_chapter_count = len(manga.chapters)
    manga.chapters = []

    chapter_order: list[str] = lsDirs(manga_path)
    chapter_archives: list[str] = lsFiles(manga_path, filters=SUPPORTED_ARCHIVE_TYPES)

    chapter_order.extend(chapter_archives)
    sort_paths(chapter_order)

    chapter_order.insert(0, manga_path) # Used to include files in the root directory

    next_chapter_number = 1
    for chapter_name in chapter_order:
        chapter_path = os.path.join(manga_path, chapter_name)
        # print(f"Scanning chapter: {chapter_path}")

        chapter: Chapter = None
        if chapter_name in chapter_archives:
            archive_name, archive_ext = os.path.splitext(chapter_name)
            archive_ext = archive_ext.lower()
            chapter = db.Chapter.create(chapter_path=chapter_path, number=next_chapter_number, title=archive_name, archive_type=archive_ext)
            db.Chapter.from_archive(chapter, archive_path=chapter_path, archive_ext=archive_ext)
        else:
            chapter = db.Chapter.create(chapter_path=chapter_path, number=next_chapter_number, title=chapter_name)
            page_names: list[str] = lsFiles(chapter_path, filters=SUPPORTED_IMAGE_TYPES)
            sort_paths(page_names)
            next_page_number = 1
            for page_name in page_names:
                page: Page = db.Page.create(file_name=page_name, number=next_page_number)
                next_page_number += 1
                chapter.pages.append(page)

        if len(chapter.pages) <= 0:
            continue
        else:
            next_chapter_number += 1
            manga.chapters.append(chapter)

    if len(manga.chapters) <= 0:
        return None

    manga.release_year = release_year_from_names([manga_name, *[chapter.title for chapter in manga.chapters]])
    if manga.new:
        manga.last_updated = manga.date_uploaded
    elif len(manga.chapters) > previous_chapter_count:
        manga.last_updated = db.getDatetimeISONow()

    return manga
            

def rescan_manga(manga: Manga) -> tuple[bool, str | None]:
    """Rebuilds the chapters and pages of one existing manga from its folder or archive.
    Returns (success, error message)."""
    manga_name = os.path.basename(os.path.normpath(manga.path))
    if os.path.isdir(manga.path):
        result = scan_manga(manga_path=manga.path, manga_name=manga_name, rescan_exisitng=True)
    elif os.path.isfile(manga.path):
        result = scan_archive_as_manga(manga.path, manga_name, rescan_exisitng=True)
    else:
        return (False, f"files not found at '{manga.path}'")

    if result is None:
        return (False, "no pages found")
    return (True, None)

# archives should be in the root folder to be their own chapter
# archives in subfolders will be ignored
def scan_manga_path(path: str, rescan_exisitng: bool = False, updated_manga: list | None = None):
    """Returns new manga. Existing manga that changed are appended to updated_manga when it's given."""
    print("Scanning:", path)

    new_manga: list[Manga] = []

    manga_to_scan: list[str] = lsDirs(path)
    found_manga_archives: list[str] = lsFiles(path, filters=SUPPORTED_ARCHIVE_TYPES)
    manga_to_scan.extend(found_manga_archives)

    for manga_name in manga_to_scan:
        manga_path = os.path.join(path, manga_name)
        manga: Manga = None

        if not os.path.isdir(manga_path):
            manga = scan_archive_as_manga(manga_path, manga_name, rescan_exisitng=rescan_exisitng)
        else:
            manga = scan_manga(manga_path=manga_path, manga_name=manga_name, rescan_exisitng=rescan_exisitng)

        if manga is not None and manga.new:
            new_manga.append(manga)
        elif manga is not None and updated_manga is not None:
            updated_manga.append(manga)

    return new_manga

def scan_library(paths: list[str]) -> dict:
    """Scans library folders for new manga and new chapters, and saves the results.
    Returns {"added": count, "updated": count}."""
    added, updated = 0, 0
    db.session.begin_nested()
    for path in paths:
        changed: list[Manga] = []
        new_manga = scan_manga_path(path, rescan_exisitng=False, updated_manga=changed)
        db.session.add_all(new_manga)
        added += len(new_manga)
        updated += len(changed)
    db.session.commit()
    db.Manga.update_manga_count()
    return {"added": added, "updated": updated}

def scan_path(path: str, rescan_exisitng: bool = False):
    if not has_path(path):
        raise ValueError(f"Server does not have access to path: '{path}'")

    new_manga: list[Manga] = []

    manga_folders: list = lsDirs(path)
    stray_archives: list = lsFiles(path, filters=SUPPORTED_ARCHIVE_TYPES)
    # Images by themselves in the root directory will not be supported
    # manga = scan_archive_as_manga(path, stray_archives, rescan_exisitng)
    for archive in stray_archives:
        archive_path = os.path.join(path, archive)
        manga: Manga = scan_archive_as_manga(archive_path, rescan_exisitng)
        if manga is not None and manga.new:
            new_manga.append(manga)

    # manga_folders.insert(0, path) # to include stray cbz or pdf files. Will also catch images
    for manga_folder in manga_folders:
        manga_path = os.path.join(path, manga_folder)
        manga: Manga = scan_manga_path(manga_path)
        if manga is not None and manga.new:
            new_manga.append(manga)

    return new_manga

def add_configured_paths(app) -> None:
    """Gives a new server (e.g. in Docker) its library: the LIBRARY_PATHS folders from the config are
    registered and scanned before requests are served.

    Only when no library folders are registered yet. An existing server keeps its own folders, so an upgraded
    install whose library lives elsewhere doesn't get the same manga added twice, and a folder the owner
    removed doesn't come back."""
    configured = app.config.get("LIBRARY_PATHS") or []
    if isinstance(configured, str):
        configured = [configured]
    with app.app_context():
        update_paths()
        if not configured or get_paths():
            return
        added = []
        for path in configured:
            path = os.path.normpath(str(path)).replace("\\", "/")
            if not os.path.isdir(path):
                print(f"LIBRARY_PATHS: '{path}' isn't a folder, skipped")
            elif not has_path(path):
                add_path(path)
                added.append(path)
        if added:
            print(f"Added library folders {added}, scanning them...")
            result = scan_library(added)
            print(f"Scan done: {result['added']} manga added")
