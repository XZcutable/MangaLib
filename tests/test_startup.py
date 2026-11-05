from mymangalib import create_app
from mymangalib.database import db
from mymangalib.models import Manga
from mymangalib.server import library_paths
from sqlalchemy import func, select

from conftest import make_library

def start(tmp_path, library_paths: str):
    config_path = tmp_path / "config.toml"
    config_path.write_text(f"""
SECRET_KEY="test-secret"
BEHIND_PROXY=false
ALLOW_NEW_USERS=false
AUTO_APPROVE_NEW_USERS=false
HIDE_MANGA=false
HIDE_TITLES=false
FETCH_BATCH_SIZE=30
DATABASE_PATH="{(tmp_path / 'test.db').as_posix()}"
LIBRARY_PATHS={library_paths}
""")
    return create_app(str(config_path))

def manga_count(app):
    with app.app_context():
        return db.session.scalar(select(func.count()).select_from(Manga))

def test_library_paths_are_added_and_scanned_on_first_start(tmp_path):
    library = tmp_path / "library"
    make_library(str(library))

    app = start(tmp_path, f"['{library.as_posix()}', '{(tmp_path / 'missing').as_posix()}']")
    with app.app_context():
        assert library_paths.get_paths() == [library.as_posix()]
    assert manga_count(app) == 2

    # A restart doesn't add the folder or its manga twice
    app = start(tmp_path, f"['{library.as_posix()}']")
    with app.app_context():
        assert library_paths.get_paths() == [library.as_posix()]
    assert manga_count(app) == 2

def test_library_paths_leave_an_existing_library_alone(tmp_path):
    """An upgraded server with its library elsewhere must not scan the same manga again from a new folder."""
    library = tmp_path / "library"
    make_library(str(library))
    app = start(tmp_path, "[]")
    with app.app_context():
        library_paths.add_path(library.as_posix())

    same_files_elsewhere = tmp_path / "mounted"
    make_library(str(same_files_elsewhere))
    app = start(tmp_path, f"['{same_files_elsewhere.as_posix()}']")
    with app.app_context():
        assert library_paths.get_paths() == [library.as_posix()]
    assert manga_count(app) == 0  # Nothing was scanned; the owner scans their own folder
