import os, zipfile

import pytest

from conftest import PASSWORD, PNG, add_volume, login, scan

def bearer(token):
    return {"Authorization": f"Bearer {token}"}

def manga_id(client, auth, title):
    items = client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]
    return next(item["id"] for item in items if item["title"] == title)

def info(client, auth, manga):
    return client.get(f"/api/v1/manga/{manga}", headers=auth).get_json()

def page(client, auth, manga, chapter, number):
    return client.get(f"/api/v1/manga/{manga}/chapters/{chapter}/pages/{number}/image", headers=auth)

def test_crunch_packs_a_folder_and_keeps_other_files(app, client, auth):
    library = app.config["TEST_LIBRARY"]
    chapter_folder = os.path.join(library, "Beta", "Chapter 1")
    with open(os.path.join(chapter_folder, "notes.txt"), "w") as notes:
        notes.write("keep me")
    beta = manga_id(client, auth, "Beta")
    client.put(f"/api/v1/manga/{beta}/progress", headers=auth, json={"chapter": 1, "page": 2})
    client.put(f"/api/v1/manga/{beta}/state", headers=auth, json={"rating": 9})
    assert info(client, auth, beta)["repack"] == {"crunchable": 1, "unpackable": 0, "job": None}

    response = client.post(f"/api/v1/manga/{beta}/crunch", headers=auth, json={})
    assert response.status_code == 202
    job = response.get_json()["job"]
    assert job["status"] == "done", job
    assert job["message"] == "Crunched 1 chapter"

    archive_path = chapter_folder + ".cbz"
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == ["ComicInfo.xml", "0001.png", "0002.png"]
    # The images are gone, the unrelated file stays
    assert os.listdir(chapter_folder) == ["notes.txt"]

    after = info(client, auth, beta)
    assert after["id"] == beta and after["chapters"][0]["format"] == "cbz"
    # Page 2 was the last page, so the series was finished before the crunch and still is
    assert after["user"]["is_read"] and after["chapters"][0]["is_read"] and after["rating"]["mine"] == 9
    assert page(client, auth, beta, 1, 2).data == PNG

def test_unpack_extracts_volumes(app, client, auth):
    library = app.config["TEST_LIBRARY"]
    alpha = manga_id(client, auth, "Alpha")
    client.put(f"/api/v1/manga/{alpha}/chapters/state", headers=auth, json={"chapters": [2], "is_read": True})
    job = client.post(f"/api/v1/manga/{alpha}/unpack", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "done" and job["done"] == 2

    names = sorted(os.listdir(os.path.join(library, "Alpha")))
    assert names == ["Alpha v01 (2019) (Digital)", "Alpha v02 (2020) (Digital)"]
    assert sorted(os.listdir(os.path.join(library, "Alpha", names[0]))) == ["0001.png", "0002.png", "0003.png"]

    after = info(client, auth, alpha)
    assert [c["format"] for c in after["chapters"]] == ["folder", "folder"]
    assert [c["is_read"] for c in after["chapters"]] == [False, True]
    assert page(client, auth, alpha, 2, 3).data == PNG

    # And back again
    job = client.post(f"/api/v1/manga/{alpha}/crunch", headers=auth, json={"chapters": [1]}).get_json()["job"]
    assert job["status"] == "done" and job["total"] == 1
    assert [c["format"] for c in info(client, auth, alpha)["chapters"]] == ["cbz", "folder"]

def test_unpack_single_archive_manga_keeps_its_id(app, client, auth):
    library = app.config["TEST_LIBRARY"]
    add_volume(library, "", "Solo.cbz", pages=2)
    scan(app, library)
    solo = manga_id(client, auth, "Solo")
    client.put(f"/api/v1/manga/{solo}/state", headers=auth, json={"is_favorite": True})

    job = client.post(f"/api/v1/manga/{solo}/unpack", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "done", job
    assert not os.path.exists(os.path.join(library, "Solo.cbz"))
    assert sorted(os.listdir(os.path.join(library, "Solo", "Solo"))) == ["0001.png", "0002.png"]
    after = info(client, auth, solo)
    assert after["user"]["is_favorite"] and after["total_chapters"] == 1
    # A full scan doesn't add it a second time
    scan(app, library)
    titles = [i["title"] for i in client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]]
    assert titles.count("Solo") == 1

def test_progress_follows_chapters_that_change_place(app, client, auth):
    """'Vol 1' sorts before 'Vol 1 extra', but 'Vol 1.cbz' sorts after it."""
    library = app.config["TEST_LIBRARY"]
    for name in ("Vol 1", "Vol 1 extra"):
        folder = os.path.join(library, "Delta", name)
        os.makedirs(folder)
        with open(os.path.join(folder, "1.png"), "wb") as image:
            image.write(PNG)
    scan(app, library)
    delta = manga_id(client, auth, "Delta")
    before = [c["title"] for c in info(client, auth, delta)["chapters"]]
    vol_1 = before.index("Vol 1") + 1
    client.put(f"/api/v1/manga/{delta}/chapters/state", headers=auth, json={"chapters": [vol_1], "is_read": True})
    client.put(f"/api/v1/manga/{delta}/progress", headers=auth, json={"chapter": vol_1, "page": 1})

    job = client.post(f"/api/v1/manga/{delta}/crunch", headers=auth, json={"chapters": [vol_1]}).get_json()["job"]
    assert job["status"] == "done", job
    after = info(client, auth, delta)
    read_titles = [c["title"] for c in after["chapters"] if c["is_read"]]
    assert read_titles == ["Vol 1"]
    assert after["chapters"][after["user"]["current_chapter"] - 1]["title"] == "Vol 1"

def test_existing_target_stops_without_touching_files(app, client, auth):
    library = app.config["TEST_LIBRARY"]
    blocker = os.path.join(library, "Beta", "Chapter 1.cbz")
    with open(blocker, "wb") as file:
        file.write(b"not a zip")
    beta = manga_id(client, auth, "Beta")
    job = client.post(f"/api/v1/manga/{beta}/crunch", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "failed" and "already exists" in job["error"]
    assert sorted(os.listdir(os.path.join(library, "Beta", "Chapter 1"))) == ["1.png", "2.png"]
    assert not [name for name in os.listdir(os.path.join(library, "Beta")) if name.endswith(".partial")]

def test_only_the_owner_can_convert(client, auth):
    client.post("/api/v1/auth/register", headers=auth, json={"username": "admin2", "password": PASSWORD})
    admin_id = next(u["id"] for u in client.get("/api/v1/admin/users", headers=auth).get_json()["users"] if u["username"] == "admin2")
    client.put(f"/api/v1/admin/users/{admin_id}", headers=auth, json={"role": "admin"})
    admin = bearer(login(client, "admin2").get_json()["token"])
    beta = manga_id(client, auth, "Beta")
    assert client.post(f"/api/v1/manga/{beta}/crunch", headers=admin, json={}).status_code == 403
    assert info(client, admin, beta)["repack"] is None
    # Nothing to unpack in a folder series
    response = client.post(f"/api/v1/manga/{beta}/unpack", headers=auth, json={})
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "nothing_to_do"
