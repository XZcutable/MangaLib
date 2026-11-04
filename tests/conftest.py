import base64, os, zipfile

import pytest

from mymangalib import create_app
from mymangalib.database import db
from mymangalib.server import api as server_api

# Smallest valid PNG (1x1 pixel)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

PASSWORD = "Passw0rd!"

def add_volume(root: str, manga: str, file_name: str, pages: int = 3):
    with zipfile.ZipFile(os.path.join(root, manga, file_name), "w") as archive:
        for page in range(1, pages + 1):
            archive.writestr(f"page{page:03}.png", PNG)

def scan(app, library_path: str):
    with app.app_context():
        for manga in server_api.scan_manga_path(library_path):
            db.session.add(manga)
        db.session.commit()

def make_library(root: str):
    """Alpha: a folder of two .cbz volumes from 2019 and 2020 with 3 pages each.
    Beta: a folder chapter of 2 images with no year in its names."""
    alpha = os.path.join(root, "Alpha")
    os.makedirs(alpha)
    for volume in (1, 2):
        add_volume(root, "Alpha", f"Alpha v0{volume} ({2018 + volume}) (Digital).cbz")

    beta_chapter = os.path.join(root, "Beta", "Chapter 1")
    os.makedirs(beta_chapter)
    for page in (1, 2):
        with open(os.path.join(beta_chapter, f"{page}.png"), "wb") as image:
            image.write(PNG)

@pytest.fixture
def app(tmp_path):
    yield make_app(tmp_path)

def make_app(tmp_path, extra_config: str = ""):
    library_path = tmp_path / "library"
    make_library(str(library_path))

    defaults = f"""
SECRET_KEY="test-secret"
BEHIND_PROXY=false
ALLOW_NEW_USERS=false
AUTO_APPROVE_NEW_USERS=false
HIDE_MANGA=false
HIDE_TITLES=false
FETCH_BATCH_SIZE=30
DATABASE_PATH="{(tmp_path / 'test.db').as_posix()}"
"""
    # A key in extra_config replaces its default (TOML doesn't allow a key twice)
    overridden = {line.split("=", 1)[0].strip() for line in extra_config.splitlines() if "=" in line}
    kept = [line for line in defaults.splitlines() if line.split("=", 1)[0].strip() not in overridden]
    config_path = tmp_path / "config.toml"
    config_path.write_text("\n".join(kept) + f"\n{extra_config}\n")
    app = create_app(str(config_path))
    app.config["TESTING"] = True
    app.config["JOBS_INLINE"] = True
    app.config["THUMBNAIL_CACHE_PATH"] = str(tmp_path / "covers")
    app.config["TEST_LIBRARY"] = library_path.as_posix()
    scan(app, app.config["TEST_LIBRARY"])
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def register(client, username, password=PASSWORD):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})

def login(client, username, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password, "device": "pytest"})

@pytest.fixture
def owner_token(client):
    register(client, "owner")
    return login(client, "owner").get_json()["token"]

@pytest.fixture
def auth(owner_token):
    return {"Authorization": f"Bearer {owner_token}"}
