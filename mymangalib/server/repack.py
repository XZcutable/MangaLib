"""Crunching (a folder of page images -> one .cbz) and unpacking (.cbz/.zip -> a folder of images).

Each conversion writes a hidden ".partial" copy next to the original, checks it, renames it into place,
and only then deletes the original. The manga keeps its id, so reading progress, ratings, tags and
read marks carry over; chapter numbers are matched up by name after the rescan."""
import os, shutil, zipfile
from typing import Optional

from sqlalchemy import select

from ..database import db
from ..models import Manga, Chapter, UserMangaData, UserChapterData
from . import comicinfo, metadata
from . import scanner

ARCHIVES = (".cbz", ".zip")

class RepackError(Exception):
    pass

def chapter_format(chapter: Chapter) -> str:
    return "folder" if chapter.archive_type is None else chapter.archive_type.lstrip(".")

def is_root_images(manga: Manga, chapter: Chapter) -> bool:
    """Images loose in the manga's own folder. They can't be crunched without changing the folder."""
    return chapter.archive_type is None and os.path.normpath(chapter.path) == os.path.normpath(manga.path)

def crunchable(manga: Manga) -> list[int]:
    return [c.number for c in manga.chapters if c.archive_type is None and not is_root_images(manga, c)]

def unpackable(manga: Manga) -> list[int]:
    return [c.number for c in manga.chapters if c.archive_type in ARCHIVES]

def _hidden_partial(path: str, suffix: str) -> str:
    """A name the scanner skips (it ignores dot files), in the same folder so the rename is instant."""
    parent, name = os.path.split(os.path.normpath(path))
    return os.path.join(parent, f".{name}{suffix}.partial")

def _remove(path: str):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)

def _page_names(chapter: Chapter) -> list[str]:
    return [page.file_name for page in sorted(chapter.pages, key=lambda page: page.number)]

def _numbered(index: int, file_name: str) -> str:
    """0001.jpg, 0002.png... so the order can never change, whatever the original names were."""
    return f"{index:04}{os.path.splitext(file_name)[1].lower()}"

def crunch_chapter(manga: Manga, chapter: Chapter):
    folder = os.path.normpath(chapter.path)
    target = folder + ".cbz"
    if os.path.exists(target):
        raise RepackError(f"{os.path.basename(target)} already exists")
    pages = _page_names(chapter)
    if not pages:
        raise RepackError(f"{os.path.basename(folder)} has no pages")

    partial = _hidden_partial(target, "")
    _remove(partial)
    existing_info = None
    info_path = os.path.join(folder, comicinfo.FILE_NAME)
    if os.path.isfile(info_path):
        with open(info_path, "rb") as file:
            existing_info = file.read()
    info = comicinfo.build(existing_info, {key: value for key, value in metadata.current(manga).items() if value})
    try:
        # Stored, not compressed: page images are already compressed, so this only costs time
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(comicinfo.FILE_NAME, info, compress_type=zipfile.ZIP_DEFLATED)
            for index, name in enumerate(pages, start=1):
                archive.write(os.path.join(folder, name), _numbered(index, name))

        with zipfile.ZipFile(partial, "r") as check:
            if check.testzip() is not None:
                raise RepackError(f"The new {os.path.basename(target)} is damaged")
            sizes = [info.file_size for info in check.infolist() if info.filename != comicinfo.FILE_NAME]
            expected = [os.path.getsize(os.path.join(folder, name)) for name in pages]
            if sizes != expected:
                raise RepackError(f"The new {os.path.basename(target)} doesn't match the original pages")
        os.replace(partial, target)
    finally:
        _remove(partial)

    # Delete only what went into the archive; anything else in the folder stays
    for name in pages:
        os.remove(os.path.join(folder, name))
    if os.path.isfile(info_path):
        os.remove(info_path)
    for root, dirs, files in os.walk(folder, topdown=False):
        if not os.listdir(root):
            os.rmdir(root)

def unpack_archive(manga: Manga, chapter: Chapter, target: str):
    """Extracts a chapter's pages into the new folder `target`, then deletes the archive."""
    archive_path = os.path.normpath(chapter.path)
    if os.path.exists(target):
        raise RepackError(f"A folder named {os.path.basename(target)} already exists")
    pages = _page_names(chapter)
    if not pages:
        raise RepackError(f"{os.path.basename(archive_path)} has no pages")

    partial = _hidden_partial(target, "")
    _remove(partial)
    try:
        os.makedirs(partial)
        with zipfile.ZipFile(archive_path, "r") as archive:
            info_name = comicinfo._entry_name(archive)
            for index, name in enumerate(pages, start=1):
                with archive.open(name) as source, open(os.path.join(partial, _numbered(index, name)), "wb") as out:
                    shutil.copyfileobj(source, out, 1024 * 1024)
            if info_name:
                with open(os.path.join(partial, comicinfo.FILE_NAME), "wb") as out:
                    out.write(archive.read(info_name))
            expected = [archive.getinfo(name).file_size for name in pages]

        written = [os.path.getsize(os.path.join(partial, _numbered(index, name))) for index, name in enumerate(pages, start=1)]
        if written != expected:
            raise RepackError(f"The pages taken out of {os.path.basename(archive_path)} don't match")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.replace(partial, target)
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise RepackError(f"Couldn't unpack {os.path.basename(archive_path)}: {error}") from error
    finally:
        _remove(partial)
    os.remove(archive_path)

def _remap_chapter_numbers(manga: Manga, old_titles: dict[int, str]):
    """The rescan numbers chapters by name order again. Moves saved positions and read marks with their chapter."""
    new_numbers = {chapter.title: chapter.number for chapter in manga.chapters}
    mapping = {old: new_numbers.get(title) for old, title in old_titles.items()}
    if all(old == new for old, new in mapping.items()):
        return
    for user_data in db.session.scalars(select(UserMangaData).where(UserMangaData.manga_id == manga.id)):
        user_data.current_chapter = mapping.get(user_data.current_chapter) or 1
    rows = db.session.scalars(select(UserChapterData).where(UserChapterData.manga_id == manga.id)).all()
    kept = {}
    for row in rows:
        db.session.delete(row)
        new = mapping.get(row.chapter_number)
        if new is not None:
            kept[(row.user_id, new)] = (row.is_read, row.read_when)
    db.session.flush()
    for (user_id, number), (is_read, read_when) in kept.items():
        db.session.add(UserChapterData(user_id=user_id, manga_id=manga.id, chapter_number=number,
                                       is_read=is_read, read_when=read_when))

def _rescan(manga: Manga, old_titles: dict[int, str]):
    success, error = scanner.rescan_manga(manga)
    if not success:
        raise RepackError(f"The files were converted, but the rescan failed: {error}")
    db.session.flush()
    _remap_chapter_numbers(manga, old_titles)
    db.session.commit()

def run(kind: str, manga_id: int, numbers: Optional[list[int]], job: dict) -> str:
    """Crunches or unpacks the given chapters (all that apply when None). Runs inside a job."""
    manga = db.session.get(Manga, manga_id)
    if manga is None:
        raise RepackError("That manga no longer exists")
    eligible = crunchable(manga) if kind == "crunch" else unpackable(manga)
    chosen = eligible if numbers is None else [n for n in numbers if n in eligible]
    if not chosen:
        raise RepackError("No chapters to convert")
    job["total"] = len(chosen)
    old_titles = {chapter.number: chapter.title for chapter in manga.chapters}
    chapters = {chapter.number: chapter for chapter in manga.chapters}

    single_archive = os.path.isfile(manga.path)
    converted, failure = 0, None
    for number in chosen:
        chapter = chapters[number]
        try:
            if kind == "crunch":
                crunch_chapter(manga, chapter)
            elif single_archive:
                # A manga that's one archive becomes a folder holding one chapter folder of the same name
                name = os.path.splitext(os.path.basename(manga.path))[0]
                new_manga_folder = os.path.join(os.path.dirname(manga.path), name)
                unpack_archive(manga, chapter, os.path.join(new_manga_folder, name))
                manga.path = new_manga_folder
            else:
                unpack_archive(manga, chapter, os.path.splitext(os.path.normpath(chapter.path))[0])
            converted += 1
            job["done"] = converted
        except (RepackError, OSError) as error:
            failure = str(error)
            break

    if converted:
        _rescan(manga, old_titles)
    if failure:
        raise RepackError(failure if not converted else f"Converted {converted}, then stopped: {failure}")
    verb = "Crunched" if kind == "crunch" else "Unpacked"
    return f"{verb} {converted} chapter{'s' if converted != 1 else ''}"
