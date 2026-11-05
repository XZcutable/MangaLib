"""Library folders that moved (stored paths rewritten) and series moved to another library folder (files moved)."""
import json, os, shutil

from sqlalchemy import select

from mymangalib import cli
from mymangalib.database import db
from mymangalib.models import Chapter, Manga
from mymangalib.server import library_paths, move

from conftest import PNG, add_volume, make_library, scan
from test_startup import manga_count, start

def manga_id(client, auth, title):
    items = client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]
    return next(item["id"] for item in items if item["title"] == title)

def info(client, auth, manga):
    return client.get(f"/api/v1/manga/{manga}", headers=auth).get_json()

def page(client, auth, manga, chapter, number):
    return client.get(f"/api/v1/manga/{manga}/chapters/{chapter}/pages/{number}/image", headers=auth)

def add_folder(client, auth, path):
    response = client.post("/api/v1/library/paths", headers=auth, json={"path": path})
    assert response.status_code == 201, response.get_json()

def stored_paths(app):
    with app.app_context():
        return sorted(db.session.scalars(select(Manga.path))) + sorted(db.session.scalars(select(Chapter.path)))

# --- Library folder moved ---

def test_moved_library_folder_keeps_reading_data(app, client, auth, tmp_path):
    library = app.config["TEST_LIBRARY"]
    add_folder(client, auth, library)
    beta = manga_id(client, auth, "Beta")
    client.put(f"/api/v1/manga/{beta}/progress", headers=auth, json={"chapter": 1, "page": 2})
    client.put(f"/api/v1/manga/{beta}/state", headers=auth, json={"rating": 8})
    before = info(client, auth, beta)

    moved = (tmp_path / "moved library").as_posix()
    os.rename(library, moved)
    response = client.put("/api/v1/library/paths", headers=auth, json={"from": library, "to": moved})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["paths"] == [moved] and body["moved"] == 2 and body["missing"] == 0

    assert all(path.replace("\\", "/").startswith(moved + "/") for path in stored_paths(app))
    after = info(client, auth, beta)
    assert after["id"] == beta and after["rating"]["mine"] == 8
    assert [after[key] for key in ("user", "resume", "progress")] == [before[key] for key in ("user", "resume", "progress")]
    assert page(client, auth, beta, 1, 2).data == PNG
    # A scan of the new folder doesn't add anything twice
    assert client.post("/api/v1/library/scan", headers=auth, json={}).get_json()["added"] == 0

def test_library_move_reports_manga_it_cant_find(app, client, auth, tmp_path):
    library = app.config["TEST_LIBRARY"]
    add_folder(client, auth, library)
    empty = tmp_path / "empty"
    empty.mkdir()
    body = client.put("/api/v1/library/paths", headers=auth, json={"from": library, "to": empty.as_posix()}).get_json()
    assert body["moved"] == 2 and body["missing"] == 2 and sorted(body["missing_titles"]) == ["Alpha", "Beta"]
    # Moving it back fixes it
    body = client.put("/api/v1/library/paths", headers=auth, json={"from": empty.as_posix(), "to": library}).get_json()
    assert body["missing"] == 0

def test_library_move_leaves_a_folder_with_a_similar_name_alone(app, client, auth, tmp_path):
    library = app.config["TEST_LIBRARY"]
    neighbour = library + "2"  # Starts with the same text, but isn't inside the library
    os.makedirs(os.path.join(neighbour, "Gamma"))
    add_volume(neighbour, "Gamma", "Gamma v01.cbz")
    scan(app, neighbour)
    add_folder(client, auth, library)
    add_folder(client, auth, neighbour)
    gamma_before = [p for p in stored_paths(app) if "Gamma" in p]

    moved = (tmp_path / "elsewhere").as_posix()
    os.rename(library, moved)
    body = client.put("/api/v1/library/paths", headers=auth, json={"from": library, "to": moved}).get_json()
    assert body["moved"] == 2
    assert [p for p in stored_paths(app) if "Gamma" in p] == gamma_before
    assert sorted(body["paths"]) == sorted([moved, neighbour])

def test_library_move_refuses_bad_folders(app, client, auth, tmp_path):
    library = app.config["TEST_LIBRARY"]
    add_folder(client, auth, library)
    other = tmp_path / "other"
    other.mkdir()
    add_folder(client, auth, other.as_posix())

    def put(old, new):
        return client.put("/api/v1/library/paths", headers=auth, json={"from": old, "to": new})

    assert put((tmp_path / "nope").as_posix(), library).status_code == 400  # Not a library folder
    assert put(library, (tmp_path / "missing").as_posix()).status_code == 400  # Not on disk
    assert put(library, other.as_posix()).status_code == 400  # Already a library folder
    assert put(library, library).status_code == 400
    assert client.put("/api/v1/library/paths", headers=auth, json={}).status_code == 400

def test_library_moves_setting_runs_once_at_startup(tmp_path):
    library = tmp_path / "library"
    make_library(str(library))
    start(tmp_path, f"['{library.as_posix()}']")  # First start: added and scanned

    mounted = tmp_path / "mounted"
    os.rename(library, mounted)
    moves = f"LIBRARY_MOVES={{'{library.as_posix()}' = '{mounted.as_posix()}'}}"
    for _ in range(2):  # Again on the next start, when it's already done
        app = start(tmp_path, f"['{mounted.as_posix()}']\n{moves}")
        with app.app_context():
            assert library_paths.get_paths() == [mounted.as_posix()]
        assert manga_count(app) == 2
        assert all(path.replace("\\", "/").startswith(mounted.as_posix() + "/") for path in stored_paths(app))

def test_library_moved_flag():
    args = cli.build_parser().parse_args(["--library-moved", "/mnt/media/manga=/var/manga"])
    assert json.loads(cli.flags_to_env(args)["FLASK_LIBRARY_MOVES"]) == {"/mnt/media/manga": "/var/manga"}

def test_rewrite_handles_roots():
    """Drive and filesystem roots end in a slash; other folders don't."""
    cases = [("D:/", "E:/manga", "D:/One/v1.cbz", "E:/manga/One/v1.cbz"),
             ("/mnt/manga", "/", "/mnt/manga/One/v1.cbz", "/One/v1.cbz"),
             ("C:/lib", "D:/lib", "C:/lib\\One\\v1.cbz", "D:/lib\\One\\v1.cbz")]
    for old, new, before, expected in cases:
        start, prefix = len(old) + 1, new
        if old.endswith("/") and not new.endswith("/"):
            prefix = new + "/"
        elif new.endswith("/") and not old.endswith("/"):
            start += 1
        assert prefix + before[start - 1:] == expected

# --- Series moved to another folder ---

def two_folders(app, client, auth, tmp_path):
    library = app.config["TEST_LIBRARY"]
    other = (tmp_path / "other").as_posix()
    os.makedirs(other)
    add_folder(client, auth, library)
    add_folder(client, auth, other)
    return library, other

def test_move_series_to_another_folder(app, client, auth, tmp_path):
    library, other = two_folders(app, client, auth, tmp_path)
    beta = manga_id(client, auth, "Beta")
    client.put(f"/api/v1/manga/{beta}/state", headers=auth, json={"is_favorite": True})

    response = client.post(f"/api/v1/manga/{beta}/move", headers=auth, json={"library_path": other})
    assert response.status_code == 202
    job = response.get_json()["job"]
    assert job["status"] == "done", job
    assert job["message"] == "Moved Beta"

    assert not os.path.exists(os.path.join(library, "Beta"))
    assert sorted(os.listdir(os.path.join(other, "Beta", "Chapter 1"))) == ["1.png", "2.png"]
    after = info(client, auth, beta)
    assert after["id"] == beta and after["user"]["is_favorite"]
    assert page(client, auth, beta, 1, 2).data == PNG
    titles = [i["title"] for i in client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]]
    client.post("/api/v1/library/scan", headers=auth, json={})
    assert sorted(i["title"] for i in client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]) == sorted(titles)

def test_move_by_copying_when_on_another_disk(app, client, auth, tmp_path, monkeypatch):
    library, other = two_folders(app, client, auth, tmp_path)
    monkeypatch.setattr(move, "_same_disk", lambda a, b: False)
    alpha = manga_id(client, auth, "Alpha")

    job = client.post(f"/api/v1/manga/{alpha}/move", headers=auth, json={"library_path": other}).get_json()["job"]
    assert job["status"] == "done", job
    assert job["done"] == job["total"] == 2
    assert not os.path.exists(os.path.join(library, "Alpha"))
    assert sorted(os.listdir(other)) == ["Alpha"]  # No .partial left behind
    assert page(client, auth, alpha, 2, 3).data == PNG

def test_move_single_archive_series(app, client, auth, tmp_path):
    library, other = two_folders(app, client, auth, tmp_path)
    add_volume(library, "", "Solo.cbz", pages=2)
    scan(app, library)
    solo = manga_id(client, auth, "Solo")

    job = client.post(f"/api/v1/manga/{solo}/move", headers=auth, json={"library_path": other}).get_json()["job"]
    assert job["status"] == "done", job
    assert os.listdir(other) == ["Solo.cbz"] and not os.path.exists(os.path.join(library, "Solo.cbz"))
    assert page(client, auth, solo, 1, 2).data == PNG

def test_failed_copy_leaves_everything_as_it_was(app, client, auth, tmp_path, monkeypatch):
    library, other = two_folders(app, client, auth, tmp_path)
    monkeypatch.setattr(move, "_same_disk", lambda a, b: False)
    copied = []

    def failing_copy(src, dst, *, follow_symlinks=True):
        if copied:
            raise OSError("disk full")
        copied.append(src)
        shutil.copyfile(src, dst)
    monkeypatch.setattr(move.shutil, "copy2", failing_copy)
    alpha = manga_id(client, auth, "Alpha")
    before = stored_paths(app)

    job = client.post(f"/api/v1/manga/{alpha}/move", headers=auth, json={"library_path": other}).get_json()["job"]
    assert job["status"] == "failed" and "disk full" in job["error"]
    assert os.listdir(other) == []
    assert len(os.listdir(os.path.join(library, "Alpha"))) == 2
    assert stored_paths(app) == before
    assert page(client, auth, alpha, 1, 1).data == PNG

def test_move_refusals(app, client, auth, tmp_path):
    library, other = two_folders(app, client, auth, tmp_path)
    beta = manga_id(client, auth, "Beta")

    def post(body):
        return client.post(f"/api/v1/manga/{beta}/move", headers=auth, json=body)

    assert post({}).status_code == 400
    assert post({"library_path": (tmp_path / "unregistered").as_posix()}).get_json()["error"]["code"] == "cant_move"
    assert "already in that folder" in post({"library_path": library}).get_json()["error"]["message"]
    os.makedirs(os.path.join(other, "Beta"))
    assert "already exists" in post({"library_path": other}).get_json()["error"]["message"]
    assert os.path.isdir(os.path.join(library, "Beta"))
