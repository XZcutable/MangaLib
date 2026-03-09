from mymangalib.helpers import validate_string
from typing import Final


import os
from ..database import db
from ..models import Path
from ..quries import QUERY_PATHS

from sqlalchemy import select

_PATHS: Final[set] = set()

#This is used when scaning for
def has_path(path: str) -> bool:
    validate_string(path)
    return db.session.scalars(QUERY_PATHS.where(Path.path == path)).one_or_none() is not None

def update_paths():
    _PATHS.clear()
    _PATHS.update(db.session.scalars(QUERY_PATHS).all())
    #[path[0] for path in Path.query.values(Path.path)]

def get_paths() -> set[str]: 
    return list(_PATHS)
    # return [path[0] for path in Path.query.values(Path.path)]

def add_path(path):
    validate_string(path)

    if has_path(path):
        raise ValueError("Path is already registered")
    elif not os.path.isdir(path):
        raise ValueError("Path is not a dir")
    else:
        path = Path(path=path)
        db.session.add(path)
        db.session.commit()
        update_paths()

def remove_path(path):
    q_path: Path = db.session.scalars(select(Path).where(Path.path == path)).one_or_none()
    if q_path is None:
        raise ValueError(f"'{path}' was not a path")
    else:
        db.session.delete(q_path)
        db.session.commit()
        update_paths()