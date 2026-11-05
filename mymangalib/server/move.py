"""Moving a series' files to another library folder.

On the same disk the folder (or archive) is renamed in one step. Across disks it's copied to a hidden
".partial" name in the target first (the scanner skips names starting with a dot), checked, renamed into
place, and only then is the original deleted. The stored paths are rewritten, so the manga keeps its id
and with it reading progress, ratings, tags and read marks."""
import os, shutil
from typing import Optional

from ..database import db
from ..models import Manga
from . import library_paths

# Room left free on the target disk after copying
SPARE_BYTES = 64 * 1024 * 1024

class MoveError(Exception):
    pass

def _size_and_count(path: str) -> tuple[int, int]:
    if os.path.isfile(path):
        return os.path.getsize(path), 1
    size = count = 0
    for folder, _dirs, files in os.walk(path):
        for name in files:
            size += os.path.getsize(os.path.join(folder, name))
            count += 1
    return size, count

def _same_disk(a: str, b: str) -> bool:
    return os.stat(a).st_dev == os.stat(b).st_dev

def _remove(path: str):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)

def check(manga: Manga, target_folder: str) -> str:
    """The new path for the manga in `target_folder`, or a MoveError saying why it can't go there."""
    registered = library_paths.registered_as(target_folder)
    if registered is None:
        raise MoveError("That folder isn't in the library")
    source = os.path.normpath(manga.path)
    if not os.path.exists(source):
        raise MoveError(f"The files aren't at '{manga.path}' any more. Rescan the library first.")
    target_folder = library_paths.normalize(registered)
    if library_paths.normalize(os.path.dirname(source)) == target_folder:
        raise MoveError("The series is already in that folder")
    if not os.path.isdir(target_folder):
        raise MoveError(f"'{target_folder}' isn't reachable on the server")
    destination = os.path.join(target_folder, os.path.basename(source))
    if os.path.exists(destination):
        raise MoveError(f"'{os.path.basename(source)}' already exists in '{target_folder}'")
    for folder in (target_folder, os.path.dirname(source)):
        if not os.access(folder, os.W_OK):
            raise MoveError(f"The server can't write to '{folder}'. If it's mounted read-only, mount it read-write.")
    if not _same_disk(os.path.dirname(source), target_folder):
        size, _count = _size_and_count(source)
        if shutil.disk_usage(target_folder).free < size + SPARE_BYTES:
            raise MoveError(f"Not enough free space in '{target_folder}'")
    return destination

def _copy(source: str, partial: str, job: dict):
    def copy_file(src, dst, *, follow_symlinks=True):
        shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
        job["done"] += 1

    if os.path.isfile(source):
        copy_file(source, partial)
    else:
        shutil.copytree(source, partial, copy_function=copy_file)
    if _size_and_count(partial) != _size_and_count(source):
        raise MoveError("The copy doesn't match the original")

def run(manga_id: int, target_folder: str, job: dict) -> Optional[str]:
    manga = db.session.get(Manga, manga_id)
    if manga is None:
        raise MoveError("The series no longer exists")
    destination = check(manga, target_folder)
    source = os.path.normpath(manga.path)
    title = manga.title

    if _same_disk(os.path.dirname(source), os.path.dirname(destination)):
        job["total"], job["done"] = 1, 0
        os.rename(source, destination)
        try:
            library_paths.rewrite_prefix(manga.path, destination)
            db.session.commit()
        except Exception:
            db.session.rollback()
            os.rename(destination, source)
            raise
        job["done"] = 1
        return f"Moved {title}"

    job["total"], job["done"] = _size_and_count(source)[1], 0
    parent, name = os.path.split(destination)
    partial = os.path.join(parent, f".{name}.move.partial")
    _remove(partial)  # Left over from an interrupted move
    try:
        _copy(source, partial, job)
        os.rename(partial, destination)
    except Exception:
        _remove(partial)
        raise
    try:
        library_paths.rewrite_prefix(manga.path, destination)
        db.session.commit()
    except Exception:
        db.session.rollback()
        _remove(destination)
        raise
    try:
        _remove(source)
    except OSError:
        pass
    if os.path.exists(source):
        # Left behind, a scan of the old folder would add the series again as a new one
        return f"Moved {title}, but couldn't delete the old copy at '{source}'. Delete it before the next scan."
    return f"Moved {title}"
