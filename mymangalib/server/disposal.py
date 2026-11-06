"""Old page images a crunch couldn't delete. They're listed for the owner, who can try deleting them again.
While a file is listed, the scanner leaves its folder out, so the images don't come back as a chapter."""
import os
from datetime import datetime, timezone

from sqlalchemy import select

from ..database import db
from ..models import PendingDeletion

def mark(files: list[tuple[str, str]], folder: str, archive: str, remove_folder: bool, manga_title: str):
    """files: (path, error). Adds them to the list (committed by the caller)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for path, error in files:
        path = os.path.normpath(path)
        row = db.session.scalar(select(PendingDeletion).where(PendingDeletion.path == path))
        if row is None:
            db.session.add(PendingDeletion(path=path, folder=os.path.normpath(folder), archive=os.path.normpath(archive),
                                           remove_folder=remove_folder, manga_title=manga_title, error=error, created=now))
        else:
            row.error = error

def pending_folders() -> set[str]:
    return set(db.session.scalars(select(PendingDeletion.folder).distinct()))

def listing() -> list[dict]:
    rows = db.session.scalars(select(PendingDeletion).order_by(PendingDeletion.manga_title, PendingDeletion.path))
    return [row.toJson() for row in rows]

def count() -> int:
    return len(db.session.scalars(select(PendingDeletion.id)).all())

def remove_empty_folder(folder: str):
    for root, _dirs, _files in os.walk(folder, topdown=False):
        try:
            if not os.listdir(root):
                os.rmdir(root)
        except OSError:
            pass

def retry() -> dict:
    """Tries to delete every listed file. A file whose .cbz is gone is kept (it's the only copy) and unlisted,
    so the next scan shows it again."""
    deleted = kept = 0
    rows = db.session.scalars(select(PendingDeletion)).all()
    for row in rows:
        if not os.path.isfile(row.archive):
            kept += 1
            db.session.delete(row)
            continue
        try:
            os.remove(row.path)
        except FileNotFoundError:
            pass
        except OSError as error:
            row.error = str(error)
            continue
        deleted += 1
        db.session.delete(row)
    db.session.flush()
    remaining_folders = pending_folders()
    for folder in {row.folder for row in rows if row.remove_folder} - remaining_folders:
        remove_empty_folder(folder)
    db.session.commit()
    return {"deleted": deleted, "kept": kept, "files": listing()}
