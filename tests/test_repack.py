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

def test_crunch_loose_images_into_the_manga_folder(app, client, auth):
    """A series that's just images: the archive goes inside its folder, so it stays the same series."""
    library = app.config["TEST_LIBRARY"]
    folder = os.path.join(library, "Loose")
    os.makedirs(folder)
    for name in ("1.png", "2.png"):
        with open(os.path.join(folder, name), "wb") as image:
            image.write(PNG)
    scan(app, library)
    loose = manga_id(client, auth, "Loose")
    client.put(f"/api/v1/manga/{loose}/chapters/state", headers=auth, json={"chapters": [1], "is_read": True})
    assert info(client, auth, loose)["repack"]["crunchable"] == 1

    job = client.post(f"/api/v1/manga/{loose}/crunch", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "done", job
    assert os.listdir(folder) == ["Loose.cbz"]
    assert not os.path.exists(os.path.join(library, "Loose.cbz"))

    after = info(client, auth, loose)
    assert [(c["title"], c["format"], c["is_read"]) for c in after["chapters"]] == [("Loose", "cbz", True)]
    assert page(client, auth, loose, 1, 2).data == PNG
    scan(app, library)
    titles = [i["title"] for i in client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]]
    assert titles.count("Loose") == 1

def test_crunch_loose_images_next_to_chapter_folders(app, client, auth):
    library = app.config["TEST_LIBRARY"]
    for folder in ("Mixed", os.path.join("Mixed", "Chapter 2")):
        os.makedirs(os.path.join(library, folder))
        with open(os.path.join(library, folder, "1.png"), "wb") as image:
            image.write(PNG)
    scan(app, library)
    mixed = manga_id(client, auth, "Mixed")
    assert info(client, auth, mixed)["repack"]["crunchable"] == 2

    job = client.post(f"/api/v1/manga/{mixed}/crunch", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "done", job
    assert sorted(os.listdir(os.path.join(library, "Mixed"))) == ["Chapter 2.cbz", "Mixed.cbz"]
    assert [c["format"] for c in info(client, auth, mixed)["chapters"]] == ["cbz", "cbz"]

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

def make_folder_series(library, name, chapters=("Chapter 1",), loose=False):
    folders = [os.path.join(library, name, chapter) for chapter in chapters]
    if loose:
        folders.append(os.path.join(library, name))
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        for page_name in ("1.png", "2.png"):
            with open(os.path.join(folder, page_name), "wb") as image:
                image.write(PNG)

def test_crunch_is_all_or_nothing(app, client, auth):
    library = app.config["TEST_LIBRARY"]
    make_folder_series(library, "Gamma2", chapters=("Ch 1", "Ch 2"))
    scan(app, library)
    gamma = manga_id(client, auth, "Gamma2")
    with open(os.path.join(library, "Gamma2", "Ch 2.cbz"), "wb") as blocker:
        blocker.write(b"not a zip")
    job = client.post(f"/api/v1/manga/{gamma}/crunch", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "failed" and "already exists" in job["error"]
    assert sorted(os.listdir(os.path.join(library, "Gamma2"))) == ["Ch 1", "Ch 2", "Ch 2.cbz"]
    assert sorted(os.listdir(os.path.join(library, "Gamma2", "Ch 1"))) == ["1.png", "2.png"]

def test_pages_stay_readable_during_the_swap(app, client, auth, monkeypatch):
    """The database switches to the archives while the old folders still exist, and the archives already do."""
    from mymangalib.server import repack, scanner
    library = app.config["TEST_LIBRARY"]
    beta = manga_id(client, auth, "Beta")
    folder = os.path.join(library, "Beta", "Chapter 1")
    seen = {}
    real_rescan = scanner.rescan_manga

    def checking_rescan(manga, skip=None):
        seen["folder"] = sorted(os.listdir(folder))
        seen["archive"] = os.path.isfile(folder + ".cbz")
        return real_rescan(manga, skip=skip)

    monkeypatch.setattr(repack.scanner, "rescan_manga", checking_rescan)
    job = client.post(f"/api/v1/manga/{beta}/crunch", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "done", job
    assert seen == {"folder": ["1.png", "2.png"], "archive": True}
    assert not os.path.exists(folder)

def test_crunch_all_preview_and_run(app, client, auth):
    library = app.config["TEST_LIBRARY"]
    make_folder_series(library, "Eps", chapters=("Ep 1", "Ep 2"))
    make_folder_series(library, "Loose2", chapters=(), loose=True)
    make_folder_series(library, "Blocked", chapters=("Part 1",))
    scan(app, library)
    with open(os.path.join(library, "Blocked", "Part 1.cbz"), "wb") as blocker:
        blocker.write(b"not a zip")

    preview = client.post("/api/v1/library/crunch/preview", headers=auth, json={}).get_json()
    by_title = {item["title"]: item for item in preview["series"]}
    assert {"Beta", "Eps", "Loose2"} <= set(by_title)
    assert by_title["Eps"]["chapters"] == 2 and by_title["Eps"]["files"] == 4
    assert by_title["Eps"]["bytes"] == 4 * len(PNG)
    assert [(s["title"], s["reason"]) for s in preview["skipped"]] == [("Blocked", "Part 1.cbz already exists")]
    assert preview["disk"]["enough"] and preview["total_chapters"] == sum(s["chapters"] for s in preview["series"])
    # The preview changes nothing
    assert sorted(os.listdir(os.path.join(library, "Eps"))) == ["Ep 1", "Ep 2"]

    ids = [item["id"] for item in preview["series"]] + [manga_id(client, auth, "Blocked")]
    response = client.post("/api/v1/library/crunch", headers=auth, json={"manga_ids": ids})
    assert response.status_code == 202
    job = response.get_json()["job"]
    assert job["status"] == "done", job
    # Blocked is checked again when its turn comes, and the rest carry on
    assert job["failures"] == [{"title": "Blocked", "error": "Part 1.cbz already exists"}]
    assert job["message"].startswith(f"Crunched {preview['total_chapters']} chapters in {len(preview['series'])} series")
    assert sorted(os.listdir(os.path.join(library, "Eps"))) == ["Ep 1.cbz", "Ep 2.cbz"]
    assert os.listdir(os.path.join(library, "Loose2")) == ["Loose2.cbz"]

    after = client.post("/api/v1/library/crunch/preview", headers=auth, json={}).get_json()
    assert after["series"] == [] and [s["title"] for s in after["skipped"]] == ["Blocked"]
    os.remove(os.path.join(library, "Blocked", "Part 1.cbz"))  # Not a real archive, so a scan can't read it
    scan(app, library)
    titles = [i["title"] for i in client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]]
    assert len(titles) == len(set(titles))

def test_crunch_all_rules(app, client, auth):
    from mymangalib.server import jobs
    response = client.post("/api/v1/library/crunch", headers=auth, json={"manga_ids": "all"})
    assert response.status_code == 400
    alpha = manga_id(client, auth, "Alpha")  # .cbz volumes only
    response = client.post("/api/v1/library/crunch", headers=auth, json={"manga_ids": [alpha]})
    assert response.get_json()["error"]["code"] == "nothing_to_do"

    # While a library-wide job runs, single-series changes wait
    fake = {"id": "fake", "kind": "crunch_all", "manga_id": None, "status": "running"}
    jobs._jobs["fake"] = fake
    jobs._order.append("fake")
    try:
        beta = manga_id(client, auth, "Beta")
        response = client.post(f"/api/v1/manga/{beta}/crunch", headers=auth, json={})
        assert response.status_code == 409 and "whole library" in response.get_json()["error"]["message"]
        assert client.get("/api/v1/library", headers=auth).get_json()["crunch_job"]["id"] == "fake"
        assert client.post("/api/v1/library/crunch", headers=auth, json={"manga_ids": [beta]}).status_code == 409
    finally:
        jobs._order.remove("fake")
        del jobs._jobs["fake"]

def test_crunch_all_is_owner_only(client, auth):
    client.post("/api/v1/auth/register", headers=auth, json={"username": "admin3", "password": PASSWORD})
    admin_id = next(u["id"] for u in client.get("/api/v1/admin/users", headers=auth).get_json()["users"] if u["username"] == "admin3")
    client.put(f"/api/v1/admin/users/{admin_id}", headers=auth, json={"role": "admin"})
    admin = bearer(login(client, "admin3").get_json()["token"])
    assert client.post("/api/v1/library/crunch/preview", headers=admin, json={}).status_code == 403
    assert client.post("/api/v1/library/crunch", headers=admin, json={"manga_ids": []}).status_code == 403

def lock_files(monkeypatch, names):
    """Makes deleting files with these names fail, like a page being read on Windows."""
    from mymangalib.server import repack
    real_remove = os.remove

    def remove(path):
        if os.path.basename(path) in names:
            raise PermissionError(13, "The file is being used by another process", path)
        real_remove(path)

    monkeypatch.setattr(os, "remove", remove)
    monkeypatch.setattr(repack.time, "sleep", lambda seconds: None)

def test_images_that_cant_be_deleted_are_listed_and_deleted_later(app, client, auth, monkeypatch):
    library = app.config["TEST_LIBRARY"]
    folder = os.path.join(library, "Beta", "Chapter 1")
    beta = manga_id(client, auth, "Beta")
    lock_files(monkeypatch, {"2.png"})
    job = client.post(f"/api/v1/manga/{beta}/crunch", headers=auth, json={}).get_json()["job"]
    assert job["status"] == "done", job
    assert "1 old file couldn't be deleted yet" in job["message"]
    assert os.listdir(folder) == ["2.png"]

    assert client.get("/api/v1/library", headers=auth).get_json()["leftover_files"] == 1
    files = client.get("/api/v1/library/leftovers", headers=auth).get_json()["files"]
    assert [(f["path"], f["manga_title"]) for f in files] == [(os.path.normpath(os.path.join(folder, "2.png")), "Beta")]
    assert "being used" in files[0]["error"]

    # Meanwhile the leftover folder isn't scanned as a chapter again
    client.post(f"/api/v1/manga/{beta}/rescan", headers=auth)
    scan(app, library)
    assert [c["format"] for c in info(client, auth, beta)["chapters"]] == ["cbz"]

    # Still locked: it stays on the list
    result = client.post("/api/v1/library/leftovers/delete", headers=auth).get_json()
    assert result["deleted"] == 0 and len(result["files"]) == 1
    monkeypatch.undo()
    result = client.post("/api/v1/library/leftovers/delete", headers=auth).get_json()
    assert result == {"deleted": 1, "kept": 0, "files": []}
    assert not os.path.exists(folder)

def test_leftovers_are_kept_when_their_archive_is_gone(app, client, auth, monkeypatch):
    library = app.config["TEST_LIBRARY"]
    folder = os.path.join(library, "Beta", "Chapter 1")
    beta = manga_id(client, auth, "Beta")
    lock_files(monkeypatch, {"1.png", "2.png"})
    client.post(f"/api/v1/manga/{beta}/crunch", headers=auth, json={})
    monkeypatch.undo()
    os.remove(folder + ".cbz")
    result = client.post("/api/v1/library/leftovers/delete", headers=auth).get_json()
    assert result == {"deleted": 0, "kept": 2, "files": []}
    assert sorted(os.listdir(folder)) == ["1.png", "2.png"]
    # Unlisted, so the images are a chapter again
    client.post(f"/api/v1/manga/{beta}/rescan", headers=auth)
    assert [c["format"] for c in info(client, auth, beta)["chapters"]] == ["folder"]

def test_leftovers_are_owner_only(client, auth):
    client.post("/api/v1/auth/register", headers=auth, json={"username": "admin4", "password": PASSWORD})
    admin_id = next(u["id"] for u in client.get("/api/v1/admin/users", headers=auth).get_json()["users"] if u["username"] == "admin4")
    client.put(f"/api/v1/admin/users/{admin_id}", headers=auth, json={"role": "admin"})
    admin = bearer(login(client, "admin4").get_json()["token"])
    assert client.get("/api/v1/library/leftovers", headers=admin).status_code == 403
    assert client.post("/api/v1/library/leftovers/delete", headers=admin).status_code == 403

def test_no_update_is_applied_while_files_are_changed(client, auth):
    from mymangalib.server import jobs
    jobs._jobs["fake"] = {"id": "fake", "kind": "crunch_all", "manga_id": None, "status": "running"}
    jobs._order.append("fake")
    try:
        response = client.post("/api/v1/admin/server/update/apply", headers=auth)
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "busy"
    finally:
        jobs._order.remove("fake")
        del jobs._jobs["fake"]

def test_crunch_all_reports_leftovers_apart_from_failures(app, client, auth, monkeypatch):
    beta = manga_id(client, auth, "Beta")
    lock_files(monkeypatch, {"2.png"})
    job = client.post("/api/v1/library/crunch", headers=auth, json={"manga_ids": [beta]}).get_json()["job"]
    assert job["status"] == "done", job
    assert job["failures"] == [] and job["leftover_files"] == 1
    assert job["message"] == "Crunched 1 chapter in 1 series. 1 old file couldn't be deleted yet (see below)"
