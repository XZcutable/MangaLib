"""Crunching (a folder of page images -> one .cbz) and unpacking (.cbz/.zip -> a folder of images).

Each conversion writes a hidden ".partial" copy next to the original, checks it, renames it into place,
and only then deletes the original. The manga keeps its id, so reading progress, ratings, tags and
read marks carry over; chapter numbers are matched up by name after the rescan."""
import os, shutil, time, zipfile
from typing import Optional

from sqlalchemy import select

from ..database import db
from ..models import Manga, Chapter, UserMangaData, UserChapterData
from . import comicinfo, disposal, metadata
from . import scanner

ARCHIVES = (".cbz", ".zip")

class RepackError(Exception):
    pass

def chapter_format(chapter: Chapter) -> str:
    return "folder" if chapter.archive_type is None else chapter.archive_type.lstrip(".")

def is_root_images(manga: Manga, chapter: Chapter) -> bool:
    """Images loose in the manga's own folder (the scanner makes them a chapter)."""
    return chapter.archive_type is None and os.path.normpath(chapter.path) == os.path.normpath(manga.path)

def crunch_target(manga: Manga, chapter: Chapter) -> str:
    """Where a chapter's .cbz goes. Loose images go inside the manga folder, named after it:
    next to the folder, the archive would be scanned as a separate manga."""
    folder = os.path.normpath(chapter.path)
    if is_root_images(manga, chapter):
        return os.path.join(folder, os.path.basename(folder) + ".cbz")
    return folder + ".cbz"

def crunchable(manga: Manga) -> list[int]:
    return [c.number for c in manga.chapters if c.archive_type is None]

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

def _new_info(manga: Manga, folder: str) -> bytes:
    existing_info = None
    info_path = os.path.join(folder, comicinfo.FILE_NAME)
    if os.path.isfile(info_path):
        with open(info_path, "rb") as file:
            existing_info = file.read()
    return comicinfo.build(existing_info, {key: value for key, value in metadata.current(manga).items() if value})

def build_archive(manga: Manga, chapter: Chapter) -> str:
    """Writes and checks the chapter's .cbz as a hidden .partial next to its target. Returns the partial's path.
    The original images are left alone."""
    folder = os.path.normpath(chapter.path)
    target = crunch_target(manga, chapter)
    if os.path.exists(target):
        raise RepackError(f"{os.path.basename(target)} already exists")
    pages = _page_names(chapter)
    if not pages:
        raise RepackError(f"{os.path.basename(folder)} has no pages")

    partial = _hidden_partial(target, "")
    _remove(partial)
    try:
        info = _new_info(manga, folder)
        # Stored, not compressed: page images are already compressed, so this only costs time
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(comicinfo.FILE_NAME, info, compress_type=zipfile.ZIP_DEFLATED)
            for index, name in enumerate(pages, start=1):
                archive.write(os.path.join(folder, name), _numbered(index, name))

        with zipfile.ZipFile(partial, "r") as check:
            if check.testzip() is not None:
                raise RepackError(f"The new {os.path.basename(target)} is damaged")
            sizes = [entry.file_size for entry in check.infolist() if entry.filename != comicinfo.FILE_NAME]
            expected = [os.path.getsize(os.path.join(folder, name)) for name in pages]
            if sizes != expected:
                raise RepackError(f"The new {os.path.basename(target)} doesn't match the original pages")
    except (OSError, zipfile.BadZipFile) as error:
        _remove(partial)
        raise RepackError(f"Couldn't pack {os.path.basename(folder)}: {error}") from error
    except BaseException:
        _remove(partial)
        raise
    return partial

def _delete_with_retry(path: str, attempts: int = 5) -> Optional[str]:
    """Windows can't delete a file while it's being read (a page being served right now), so retry briefly.
    Returns the error when the file couldn't be deleted."""
    for attempt in range(attempts):
        try:
            os.remove(path)
            return None
        except FileNotFoundError:
            return None
        except OSError as error:
            if attempt == attempts - 1 or not isinstance(error, PermissionError):
                return str(error)
            time.sleep(0.2)

def delete_originals(folder: str, pages: list[str], root_images: bool) -> list[tuple[str, str]]:
    """Deletes only what went into the archive; anything else in the folder stays.
    Returns (path, error) for each file that couldn't be deleted."""
    failed = []
    for path in [os.path.join(folder, name) for name in pages] + [os.path.join(folder, comicinfo.FILE_NAME)]:
        error = _delete_with_retry(path)
        if error:
            failed.append((path, error))
    if not root_images and not failed:
        # The manga folder holds the new archive and maybe other chapters, so only chapter folders are removed
        disposal.remove_empty_folder(folder)
    return failed

def crunch_series(manga: Manga, numbers: list[int], job: dict, done_before: int = 0) -> tuple[int, list[str]]:
    """Packs the given image-folder chapters of one manga, all or nothing, with no moment where pages
    can't be read: the archives are built and put in place first, the database switches to them in one
    commit (the rescan leaves the old folders out), and only then are the old images deleted.
    Returns (chapters converted, problems deleting the old images)."""
    chapters = {chapter.number: chapter for chapter in manga.chapters}
    old_titles = {chapter.number: chapter.title for chapter in manga.chapters}
    chosen = [chapters[number] for number in numbers]
    for chapter in chosen:
        if is_root_images(manga, chapter):
            # After the rescan the chapter is titled after its archive, so match it by that name
            new_title = os.path.splitext(os.path.basename(crunch_target(manga, chapter)))[0]
            if any(c.title == new_title for c in manga.chapters if c is not chapter):
                raise RepackError(f"A chapter named {new_title} already exists")
            old_titles[chapter.number] = new_title

    built: list[tuple[str, str]] = []  # (partial, target)
    placed: list[str] = []
    try:
        for index, chapter in enumerate(chosen, start=1):
            built.append((build_archive(manga, chapter), crunch_target(manga, chapter)))
            job["done"] = done_before + index
        for partial, target in built:
            if os.path.exists(target):
                raise RepackError(f"{os.path.basename(target)} already exists")
            os.replace(partial, target)
            placed.append(target)
    except BaseException as error:
        for partial, _target in built:
            _remove(partial)
        for target in placed:
            _remove(target)  # The originals are all still there
        if isinstance(error, OSError):
            raise RepackError(f"Couldn't put the new archives in place: {error}") from error
        raise

    # What to delete afterwards, read before the rescan replaces the chapter rows
    originals = [(os.path.normpath(c.path), _page_names(c), is_root_images(manga, c)) for c in chosen]
    try:
        _rescan(manga, old_titles, skip={folder for folder, _pages, _root in originals})
    except BaseException:
        db.session.rollback()
        for target in placed:
            _remove(target)
        raise

    left = 0
    for (folder, pages, root_images), (_partial, target) in zip(originals, built):
        failed = delete_originals(folder, pages, root_images)
        if failed:
            # Listed in Settings for the owner to delete later; the scanner leaves the folder out meanwhile
            disposal.mark(failed, folder, target, remove_folder=not root_images, manga_title=manga.title)
            left += len(failed)
    problems = []
    if left:
        db.session.commit()
        problems.append(f"{left} old file{'s' if left != 1 else ''} couldn't be deleted yet; "
                        "they're listed in Settings, under Library.")
    return len(chosen), problems

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

def _rescan(manga: Manga, old_titles: dict[int, str], skip: Optional[set[str]] = None):
    success, error = scanner.rescan_manga(manga, skip=skip)
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

    if kind == "crunch":
        converted, problems = crunch_series(manga, chosen, job)
        message = f"Crunched {converted} chapter{'s' if converted != 1 else ''}"
        return " ".join([message, *problems])

    old_titles = {chapter.number: chapter.title for chapter in manga.chapters}
    chapters = {chapter.number: chapter for chapter in manga.chapters}
    single_archive = os.path.isfile(manga.path)
    converted, failure = 0, None
    for number in chosen:
        chapter = chapters[number]
        try:
            if single_archive:
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
    return f"Unpacked {converted} chapter{'s' if converted != 1 else ''}"

# --- Crunching the whole library ---

def _series_problem(manga: Manga, numbers: list[int]) -> Optional[str]:
    """Why a series' crunch would fail before it starts, or None."""
    chapters = {chapter.number: chapter for chapter in manga.chapters}
    for number in numbers:
        chapter = chapters[number]
        target = crunch_target(manga, chapter)
        if os.path.exists(target):
            return f"{os.path.basename(target)} already exists"
        if not os.path.isdir(chapter.path):
            return f"The folder {os.path.basename(os.path.normpath(chapter.path))} is missing"
        if is_root_images(manga, chapter):
            new_title = os.path.splitext(os.path.basename(target))[0]
            if any(c.title == new_title for c in manga.chapters if c is not chapter):
                return f"A chapter named {new_title} already exists"
    return None

def _series_size(manga: Manga, numbers: list[int]) -> tuple[int, int]:
    """(page files, bytes) of the chapters that would be packed."""
    chapters = {chapter.number: chapter for chapter in manga.chapters}
    files = size = 0
    for number in numbers:
        chapter = chapters[number]
        for name in _page_names(chapter):
            try:
                size += os.path.getsize(os.path.join(chapter.path, name))
                files += 1
            except OSError:
                pass
    return files, size

def crunch_preview() -> dict:
    """What crunching every series would do, without touching any file."""
    series, skipped = [], []
    needed, free = 0, None
    for manga in db.session.scalars(select(Manga).order_by(Manga.title)):
        numbers = crunchable(manga)
        if not numbers:
            continue
        problem = _series_problem(manga, numbers)
        if problem:
            skipped.append({"id": manga.id, "title": manga.title, "reason": problem})
            continue
        files, size = _series_size(manga, numbers)
        series.append({"id": manga.id, "title": manga.title, "chapters": len(numbers), "files": files, "bytes": size})
        # A series' archives are all written before its images are deleted, so the biggest one sets the space needed
        needed = max(needed, size)
        try:
            space = shutil.disk_usage(manga.path).free
            free = space if free is None else min(free, space)
        except OSError:
            pass
    return {
        "series": series,
        "skipped": skipped,
        "total_chapters": sum(item["chapters"] for item in series),
        "total_bytes": sum(item["bytes"] for item in series),
        "disk": {"needed": needed, "free": free, "enough": free is None or free >= needed},
    }

def eligible_for_crunch_all(ids: list[int]) -> list[tuple[int, int]]:
    """(manga id, chapter count) for the given series that still have something to crunch."""
    found = []
    for manga_id in ids:
        manga = db.session.get(Manga, manga_id)
        numbers = crunchable(manga) if manga is not None else []
        if numbers:
            found.append((manga_id, len(numbers)))
    return found

def crunch_all(ids: list[int], job: dict) -> str:
    """Crunches each series in turn. A series that fails is left as it was and the rest carry on."""
    job["failures"] = []
    job["current"] = None
    done_series = done_chapters = converted_chapters = 0
    for manga_id in ids:
        manga = db.session.get(Manga, manga_id)
        numbers = crunchable(manga) if manga is not None else []
        if not numbers:
            continue
        job["current"] = manga.title
        title = manga.title
        try:
            problem = _series_problem(manga, numbers)
            if problem:
                raise RepackError(problem)
            converted, problems = crunch_series(manga, numbers, job, done_before=done_chapters)
            done_series += 1
            done_chapters += converted
            converted_chapters += converted
            # Old files it couldn't delete are listed in Settings (disposal), not counted as failures
        except Exception as error:
            db.session.rollback()
            job["failures"].append({"title": title, "error": str(error) or error.__class__.__name__})
            # Count its chapters as handled, so the progress still reaches the end
            done_chapters += len(numbers)
        job["done"] = done_chapters
    job["current"] = None
    message = (f"Crunched {converted_chapters} chapter{'s' if converted_chapters != 1 else ''} "
               f"in {done_series} series")
    if job["failures"]:
        message += f"; {len(job['failures'])} left as they were"
    leftovers = disposal.count()
    job["leftover_files"] = leftovers
    if leftovers:
        message += f". {leftovers} old file{'s' if leftovers != 1 else ''} couldn't be deleted yet (see below)"
    return message
