import os, zipfile

import pytest

from conftest import PASSWORD, PNG, login, make_app, scan
from mymangalib import create_app
from mymangalib.server import comicinfo

COMIC_INFO = b"""<?xml version="1.0" encoding="utf-8"?>
<ComicInfo>
  <Series>Gamma Series</Series>
  <Number>1</Number>
  <Summary>A test story.</Summary>
  <Year>2015</Year>
  <Writer>Someone</Writer>
  <Genre>Action, Comedy</Genre>
  <Manga>YesAndRightToLeft</Manga>
  <Pages><Page Image="0" Type="FrontCover" /></Pages>
</ComicInfo>"""

def bearer(token):
    return {"Authorization": f"Bearer {token}"}

def add_gamma(library: str):
    """Gamma: one .cbz volume with a ComicInfo.xml."""
    os.makedirs(os.path.join(library, "Gamma"))
    path = os.path.join(library, "Gamma", "Gamma v01.cbz")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ComicInfo.xml", COMIC_INFO)
        for page in (1, 2):
            archive.writestr(f"{page:03}.png", PNG)
    return path

@pytest.fixture
def gamma(app):
    path = add_gamma(app.config["TEST_LIBRARY"])
    scan(app, app.config["TEST_LIBRARY"])
    return path

@pytest.fixture
def reader(client, auth):
    client.post("/api/v1/auth/register", headers=auth, json={"username": "reader", "password": PASSWORD})
    return bearer(login(client, "reader").get_json()["token"])

def manga_id(client, auth, title):
    items = client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]
    return next(item["id"] for item in items if item["title"] == title)

def test_comicinfo_round_trip_keeps_volume_fields():
    fields = comicinfo.parse(COMIC_INFO)
    assert fields["genres"] == ["Action", "Comedy"] and fields["reading_direction"] == "rtl" and fields["year"] == 2015

    rebuilt = comicinfo.build(COMIC_INFO, {"summary": None, "artist": "Penciller Person", "genres": ["Drama"]})
    parsed = comicinfo.parse(rebuilt)
    assert "summary" not in parsed and parsed["artist"] == "Penciller Person" and parsed["genres"] == ["Drama"]
    text = rebuilt.decode()
    # Per-volume details survive and new elements go in schema order
    assert "<Number>1</Number>" in text and "<Page " in text
    assert text.index("<Writer>") < text.index("<Penciller>") < text.index("<Genre>") < text.index("<Pages>")

def test_scan_reads_comicinfo(client, auth, gamma):
    info = client.get(f"/api/v1/manga/{manga_id(client, auth, 'Gamma')}", headers=auth).get_json()
    assert info["title"] == "Gamma"  # the folder name stays the title
    assert info["metadata"]["summary"] == "A test story."
    assert info["metadata"]["genres"] == ["Action", "Comedy"]
    assert info["metadata"]["reading_direction"] == "rtl"
    assert info["release_year"] == 2015
    assert info["reading_hint"] == {"mode": None, "direction": "rtl"}

def test_webtoon_format_opens_vertically(client, auth):
    beta = manga_id(client, auth, "Beta")
    client.patch(f"/api/v1/manga/{beta}", headers=auth, json={"metadata": {"format": "Webtoon"}})
    assert client.get(f"/api/v1/manga/{beta}", headers=auth).get_json()["reading_hint"]["mode"] == "vertical"

def test_existing_databases_read_comicinfo_at_startup(tmp_path):
    app = make_app(tmp_path)
    add_gamma(app.config["TEST_LIBRARY"])
    scan(app, app.config["TEST_LIBRARY"])
    with app.app_context():
        from mymangalib.database import db
        from sqlalchemy import text
        db.session.execute(text("UPDATE manga_metadata SET summary = NULL, metadata_source = NULL"))
        db.session.commit()

    # Starting the server again reads the files for manga that haven't been checked
    again = create_app(str(tmp_path / "config.toml"))
    with again.app_context():
        from mymangalib.database import db
        from mymangalib.models import MangaMetadata
        sources = {row.metadata_source for row in db.session.query(MangaMetadata)}
        summaries = {row.summary for row in db.session.query(MangaMetadata)}
    assert sources == {"file", "none"} and "A test story." in summaries

def test_suggestion_needs_approval_then_writes_files(client, auth, reader, gamma):
    gamma_id = manga_id(client, auth, "Gamma")
    response = client.post(f"/api/v1/manga/{gamma_id}/metadata/suggestions", headers=reader,
                           json={"changes": {"summary": "Better summary", "writer": "Someone", "artist": "Artist"}})
    assert response.status_code == 201
    # Fields that wouldn't change are dropped
    assert response.get_json()["suggestion"]["changes"] == {"summary": "Better summary", "artist": "Artist"}

    # Nothing changes until an admin approves; the user sees their pending suggestion
    info = client.get(f"/api/v1/manga/{gamma_id}", headers=reader).get_json()
    assert info["metadata"]["summary"] == "A test story."
    assert info["my_suggestion"]["changes"]["summary"] == "Better summary"
    assert client.get("/api/v1/auth/me", headers=auth).get_json()["user"]["pending_suggestions"] == 1

    # Users can't review
    pending = client.get("/api/v1/admin/metadata/suggestions", headers=auth).get_json()["suggestions"]
    assert pending[0]["current"] == {"summary": "A test story.", "artist": None}
    assert pending[0]["username"] == "reader" and pending[0]["manga_title"] == "Gamma"
    assert client.post(f"/api/v1/admin/metadata/suggestions/{pending[0]['id']}/approve", headers=reader).status_code == 403

    result = client.post(f"/api/v1/admin/metadata/suggestions/{pending[0]['id']}/approve", headers=auth).get_json()
    assert result["suggestion"]["status"] == "approved"
    assert result["job"]["status"] == "done" and result["job"]["done"] == 1

    info = client.get(f"/api/v1/manga/{gamma_id}", headers=reader).get_json()
    assert info["metadata"]["summary"] == "Better summary" and info["my_suggestion"] is None
    written = comicinfo.read_archive(gamma)
    assert written["summary"] == "Better summary" and written["artist"] == "Artist" and written["writer"] == "Someone"
    with zipfile.ZipFile(gamma) as archive:
        assert "<Number>1</Number>" in archive.read("ComicInfo.xml").decode()
    # Pages still load from the rewritten archive
    page = client.get(f"/api/v1/manga/{gamma_id}/chapters/1/pages/2/image", headers=reader)
    assert page.status_code == 200 and page.data == PNG

def test_summary_goes_into_the_first_volume_only(client, auth, gamma):
    second = os.path.join(os.path.dirname(gamma), "Gamma v02.cbz")
    with zipfile.ZipFile(second, "w") as archive:
        archive.writestr("ComicInfo.xml", COMIC_INFO.replace(b"A test story.", b"Volume two story."))
        archive.writestr("001.png", PNG)
    gamma_id = manga_id(client, auth, "Gamma")
    assert client.post(f"/api/v1/manga/{gamma_id}/rescan", headers=auth).status_code == 200

    client.patch(f"/api/v1/manga/{gamma_id}", headers=auth,
                 json={"metadata": {"summary": "Series summary", "publisher": "Pub"}})
    first, other = comicinfo.read_archive(gamma), comicinfo.read_archive(second)
    assert first["summary"] == "Series summary" and first["publisher"] == "Pub"
    assert other["summary"] == "Volume two story." and other["publisher"] == "Pub"

def test_rejected_suggestion_changes_nothing(client, auth, reader, gamma):
    gamma_id = manga_id(client, auth, "Gamma")
    suggestion = client.post(f"/api/v1/manga/{gamma_id}/metadata/suggestions", headers=reader,
                             json={"changes": {"summary": "Wrong"}}).get_json()["suggestion"]
    before = os.path.getmtime(gamma)
    result = client.post(f"/api/v1/admin/metadata/suggestions/{suggestion['id']}/reject", headers=auth).get_json()
    assert result["suggestion"]["status"] == "rejected" and result["job"] is None
    assert client.get(f"/api/v1/manga/{gamma_id}", headers=reader).get_json()["metadata"]["summary"] == "A test story."
    assert os.path.getmtime(gamma) == before
    # It can't be reviewed twice
    assert client.post(f"/api/v1/admin/metadata/suggestions/{suggestion['id']}/approve", headers=auth).status_code == 404

def test_admin_edit_writes_folder_series(client, auth):
    beta = manga_id(client, auth, "Beta")
    result = client.patch(f"/api/v1/manga/{beta}", headers=auth,
                          json={"metadata": {"genres": ["Slice of Life"], "year": 2001, "reading_direction": "rtl"}}).get_json()
    assert result["metadata"]["genres"] == ["Slice of Life"] and result["job"]["status"] == "done"
    info = client.get(f"/api/v1/manga/{beta}", headers=auth).get_json()
    assert info["release_year"] == 2001
    folder = os.path.join(client.application.config["TEST_LIBRARY"], "Beta")
    assert comicinfo.read_folder(folder)["genres"] == ["Slice of Life"]

def test_suggestion_validation(client, auth, reader):
    beta = manga_id(client, auth, "Beta")
    post = lambda changes: client.post(f"/api/v1/manga/{beta}/metadata/suggestions", headers=reader, json={"changes": changes})
    assert post({"path": "/etc"}).status_code == 400
    assert post({"year": "2020"}).status_code == 400
    assert post({"web": "javascript:alert(1)"}).status_code == 400
    assert post({"reading_direction": "up"}).status_code == 400
    assert post({"genres": ["a,b"]}).status_code == 400
    assert post({"title": ""}).status_code == 400
    assert post({"summary": None}).get_json()["error"]["code"] == "nothing_changed"
    # A second suggestion replaces the first
    post({"summary": "One"})
    post({"summary": "Two"})
    pending = client.get("/api/v1/admin/metadata/suggestions", headers=auth).get_json()["suggestions"]
    assert [s["changes"] for s in pending] == [{"summary": "Two"}]
    assert client.delete(f"/api/v1/manga/{beta}/metadata/suggestions/mine", headers=reader).status_code == 200
    assert client.get("/api/v1/admin/metadata/suggestions", headers=auth).get_json()["suggestions"] == []
