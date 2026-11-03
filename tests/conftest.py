import base64, os, zipfile

import pytest

from mymangalib import create_app
from mymangalib.database import db
from mymangalib.server import api as server_api

# Smallest valid PNG (1x1 pixel)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

PASSWORD = "Passw0rd!"

def make_library(root: str):
    """Alpha: a folder of two .cbz volumes with 3 pages each. Beta: a folder chapter of 2 images."""
    alpha = os.path.join(root, "Alpha")
    os.makedirs(alpha)
    for volume in (1, 2):
        with zipfile.ZipFile(os.path.join(alpha, f"Alpha v0{volume}.cbz"), "w") as archive:
            for page in (1, 2, 3):
                archive.writestr(f"page{page:03}.png", PNG)

    beta_chapter = os.path.join(root, "Beta", "Chapter 1")
    os.makedirs(beta_chapter)
    for page in (1, 2):
        with open(os.path.join(beta_chapter, f"{page}.png"), "wb") as image:
            image.write(PNG)

@pytest.fixture
def app(tmp_path):
    library_path = tmp_path / "library"
    make_library(str(library_path))

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
""")
    app = create_app(str(config_path))
    app.config["TESTING"] = True
    app.config["THUMBNAIL_CACHE_PATH"] = str(tmp_path / "covers")

    with app.app_context():
        for manga in server_api.scan_manga_path(library_path.as_posix()):
            db.session.add(manga)
        db.session.commit()

    yield app

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
