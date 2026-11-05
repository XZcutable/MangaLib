import os

import pytest

from conftest import PASSWORD, add_volume, login

def bearer(token):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def reader(client, auth):
    """An approved normal user, created by the owner (admin-created users are approved)."""
    response = client.post("/api/v1/auth/register", headers=auth, json={"username": "reader", "password": PASSWORD})
    assert response.status_code == 201 and response.get_json()["user"]["approved"]
    return {"id": response.get_json()["user"]["id"], "headers": bearer(login(client, "reader").get_json()["token"])}

def manga_id(client, auth, title):
    items = client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]
    return next(item["id"] for item in items if item["title"] == title)

# --- Access rules ---

@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/admin/users"),
    ("post", "/api/v1/tags"),
    ("patch", "/api/v1/manga/1"),
    ("get", "/api/v1/library"),
    ("post", "/api/v1/library/scan"),
    ("delete", "/api/v1/manga/1"),
    ("put", "/api/v1/server/config"),
])
def test_normal_users_get_403(client, reader, method, path):
    response = getattr(client, method)(path, headers=reader["headers"], json={})
    assert response.status_code == 403

def test_admin_can_manage_users_but_only_owner_changes_roles(client, auth, reader):
    response = client.put(f"/api/v1/admin/users/{reader['id']}", headers=auth, json={"role": "admin"})
    assert response.get_json()["user"]["is_admin"]

    # reader is now an admin: can list users, can't hand out roles or touch the owner
    assert client.get("/api/v1/admin/users", headers=reader["headers"]).status_code == 200
    client.post("/api/v1/auth/register", headers=auth, json={"username": "third", "password": PASSWORD})
    third = next(u for u in client.get("/api/v1/admin/users", headers=auth).get_json()["users"] if u["username"] == "third")
    assert client.put(f"/api/v1/admin/users/{third['id']}", headers=reader["headers"], json={"role": "admin"}).status_code == 403
    assert client.put("/api/v1/admin/users/1", headers=reader["headers"], json={"approved": False}).status_code == 403
    assert client.put(f"/api/v1/admin/users/{third['id']}", headers=auth, json={"role": "owner"}).status_code == 400

def test_unapproving_a_user_signs_them_out(client, auth, reader):
    client.put(f"/api/v1/admin/users/{reader['id']}", headers=auth, json={"approved": False})
    assert client.get("/api/v1/auth/me", headers=reader["headers"]).status_code == 401
    assert login(client, "reader").status_code == 403

def test_pending_signups_can_be_approved(app, client, auth):
    app.config["ALLOW_NEW_USERS"] = True
    client.post("/api/v1/auth/register", json={"username": "newbie", "password": PASSWORD})
    users = client.get("/api/v1/admin/users", headers=auth).get_json()["users"]
    newbie = next(u for u in users if u["username"] == "newbie")
    assert users[0]["username"] == "newbie"  # pending users are listed first
    client.put(f"/api/v1/admin/users/{newbie['id']}", headers=auth, json={"approved": True})
    assert login(client, "newbie").status_code == 200

# --- Account ---

def test_change_password_signs_out_other_devices(client, auth, owner_token):
    other = bearer(login(client, "owner").get_json()["token"])
    bad = client.put("/api/v1/auth/password", headers=auth, json={"current_password": "nope", "new_password": "N3w!pass"})
    assert bad.status_code == 403
    weak = client.put("/api/v1/auth/password", headers=auth, json={"current_password": PASSWORD, "new_password": "short"})
    assert weak.get_json()["error"]["code"] == "weak_password"

    ok = client.put("/api/v1/auth/password", headers=auth, json={"current_password": PASSWORD, "new_password": "N3w!pass"})
    assert ok.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200
    assert client.get("/api/v1/auth/me", headers=other).status_code == 401
    assert login(client, "owner", "N3w!pass").status_code == 200

def test_change_username(client, auth, reader):
    assert client.put("/api/v1/auth/username", headers=auth, json={"username": "READER"}).status_code == 409
    response = client.put("/api/v1/auth/username", headers=auth, json={"username": "boss"})
    assert response.get_json()["user"]["username"] == "boss"
    # Spaces around a new name are removed; a blank name isn't allowed
    response = client.put("/api/v1/auth/username", headers=auth, json={"username": "  chief "})
    assert response.get_json()["user"]["username"] == "chief"
    assert client.put("/api/v1/auth/username", headers=auth, json={"username": "   "}).status_code == 400

def test_admin_can_require_a_username_change(client, auth, reader):
    response = client.put(f"/api/v1/admin/users/{reader['id']}", headers=auth, json={"must_change_username": True})
    assert response.get_json()["user"]["must_change_username"] is True

    # Until then the reader can only see their account, rename, or log out
    headers = reader["headers"]
    me = client.get("/api/v1/auth/me", headers=headers).get_json()["user"]
    assert me["must_change_username"] is True
    blocked = client.get("/api/v1/manga?list=all", headers=headers)
    assert blocked.status_code == 403 and blocked.get_json()["error"]["code"] == "username_change_required"
    assert client.get("/api/v1/manga/1/cover", headers=headers).status_code == 403

    # Keeping the same name doesn't count
    response = client.put("/api/v1/auth/username", headers=headers, json={"username": "reader"})
    assert response.status_code == 400

    response = client.put("/api/v1/auth/username", headers=headers, json={"username": "reader2"})
    assert response.get_json()["user"] == {**me, "username": "reader2", "must_change_username": False}
    assert client.get("/api/v1/manga?list=all", headers=headers).status_code == 200

def test_admin_can_clear_a_required_username_change(client, auth, reader):
    client.put(f"/api/v1/admin/users/{reader['id']}", headers=auth, json={"must_change_username": True})
    client.put(f"/api/v1/admin/users/{reader['id']}", headers=auth, json={"must_change_username": False})
    assert client.get("/api/v1/manga?list=all", headers=reader["headers"]).status_code == 200

def test_classic_ui_sends_flagged_users_to_settings(client, auth, reader):
    client.put(f"/api/v1/admin/users/{reader['id']}", headers=auth, json={"must_change_username": True})
    client.post("/login", data={"username": "reader", "password": PASSWORD})

    response = client.get("/manga/all")
    assert response.status_code == 302 and response.headers["Location"].endswith("/settings")
    assert client.get("/settings").status_code == 200

    client.post("/auth/change-username", data={"new-username": " renamed "})
    assert client.get("/manga/all").status_code == 200

# --- Tags ---

def test_tags_lifecycle(client, auth):
    assert client.post("/api/v1/tags", headers=auth, json={"tag": "Slice Of Life"}).status_code == 201
    assert client.post("/api/v1/tags", headers=auth, json={"tag": "slice of life"}).status_code == 409
    assert client.post("/api/v1/tags", headers=auth, json={"tag": "gore", "nsfw": True}).status_code == 201
    assert client.post("/api/v1/tags", headers=auth, json={"tag": "bad-tag!"}).status_code == 400

    alpha = manga_id(client, auth, "Alpha")
    response = client.put(f"/api/v1/manga/{alpha}/tags", headers=auth, json={"tags": ["gore", "slice of life"]})
    assert [tag["tag"] for tag in response.get_json()["tags"]] == ["gore", "slice of life"]
    assert client.put(f"/api/v1/manga/{alpha}/tags", headers=auth, json={"tags": ["missing"]}).status_code == 400

    found = client.get("/api/v1/manga/search?q=tag:slice_of_life", headers=auth).get_json()["items"]
    assert [item["title"] for item in found] == ["Alpha"]

    assert client.delete("/api/v1/tags/gore", headers=auth).status_code == 200
    info = client.get(f"/api/v1/manga/{alpha}", headers=auth).get_json()
    assert [tag["tag"] for tag in info["tags"]] == ["slice of life"]

# --- Manga ---

def test_rename_and_reset_title(client, auth):
    alpha = manga_id(client, auth, "Alpha")
    assert client.patch(f"/api/v1/manga/{alpha}", headers=auth, json={"title": "  "}).status_code == 400
    assert client.patch(f"/api/v1/manga/{alpha}", headers=auth, json={"title": "Alpha Saga"}).get_json()["title"] == "Alpha Saga"
    assert client.patch(f"/api/v1/manga/{alpha}", headers=auth, json={"title": None}).get_json()["title"] == "Alpha"

def test_owner_sees_path_others_dont(client, auth, reader):
    alpha = manga_id(client, auth, "Alpha")
    assert client.get(f"/api/v1/manga/{alpha}", headers=auth).get_json()["path"].endswith("Alpha")
    assert client.get(f"/api/v1/manga/{alpha}", headers=reader["headers"]).get_json()["path"] is None

def test_delete_and_rescan(app, client, auth):
    alpha = manga_id(client, auth, "Alpha")
    add_volume(app.config["TEST_LIBRARY"], "Alpha", "Alpha v03 (2021).cbz")
    rescanned = client.post(f"/api/v1/manga/{alpha}/rescan", headers=auth).get_json()
    assert rescanned["total_chapters"] == 3

    assert client.delete(f"/api/v1/manga/{alpha}", headers=auth).status_code == 200
    assert client.get(f"/api/v1/manga/{alpha}", headers=auth).status_code == 404

# --- Library ---

def test_library_paths_browse_and_scan(app, client, auth, tmp_path):
    library = app.config["TEST_LIBRARY"]
    assert client.get("/api/v1/library", headers=auth).get_json()["paths"] == []
    assert client.post("/api/v1/library/paths", headers=auth, json={"path": str(tmp_path / "nope")}).status_code == 400

    response = client.post("/api/v1/library/paths", headers=auth, json={"path": library})
    assert response.status_code == 201 and response.get_json()["paths"] == [library]

    browse = client.get(f"/api/v1/library/browse?dir={library}", headers=auth).get_json()
    assert [folder["name"] for folder in browse["folders"]] == ["Alpha", "Beta"]
    assert browse["parent"] == os.path.dirname(library).replace("\\", "/")
    assert client.get("/api/v1/library/browse", headers=auth).get_json()["folders"]

    # A new series and a new volume
    os.makedirs(os.path.join(library, "Gamma"))
    add_volume(library, "Gamma", "Gamma v01.cbz")
    add_volume(library, "Alpha", "Alpha v03 (2021).cbz")
    result = client.post("/api/v1/library/scan", headers=auth, json={}).get_json()
    assert result == {"added": 1, "updated": 1}
    assert client.post("/api/v1/library/scan", headers=auth, json={}).get_json() == {"added": 0, "updated": 0}

    assert client.delete(f"/api/v1/library/paths?path={library}", headers=auth).get_json()["paths"] == []

def test_server_config_toggles(client, auth):
    assert client.put("/api/v1/server/config", headers=auth, json={"hide_titles": True}).get_json() == {
        "allow_new_users": False, "auto_approve_new_users": False, "hide_manga": False, "hide_titles": True,
        "site_name": "myMangaLib", "auto_update": True, "auto_update_locked": False,
    }
    assert client.get("/api/v1/server/info").get_json()["hide_titles"] is True
    client.put("/api/v1/server/config", headers=auth, json={"hide_titles": False})

def test_owner_renames_the_site(app, client, auth, reader, tmp_path):
    info = client.get("/api/v1/server/info").get_json()
    assert info["site_name"] == "myMangaLib" and info["name"] == "myMangaLib"

    response = client.put("/api/v1/server/config", headers=auth, json={"site_name": "  Reuben's   Manga "})
    assert response.get_json()["site_name"] == "Reuben's Manga"
    info = client.get("/api/v1/server/info").get_json()
    # The app still recognizes the server by "name"
    assert info["site_name"] == "Reuben's Manga" and info["name"] == "myMangaLib"

    # The classic pages use it in the browser tab
    client.post("/login", data={"username": "owner", "password": PASSWORD})
    assert "- Reuben&#39;s Manga</title>" in client.get("/manga/all").get_data(as_text=True)

    # Saved, so it survives a restart
    from mymangalib import create_app
    restarted = create_app(str(tmp_path / "config.toml"))
    assert restarted.test_client().get("/api/v1/server/info").get_json()["site_name"] == "Reuben's Manga"

    # Only the owner, not too long, and empty goes back to the default
    assert client.put("/api/v1/server/config", headers=reader["headers"], json={"site_name": "Mine"}).status_code == 403
    assert client.put("/api/v1/server/config", headers=auth, json={"site_name": "x" * 41}).status_code == 400
    assert client.put("/api/v1/server/config", headers=auth, json={"site_name": 5}).status_code == 400
    assert client.put("/api/v1/server/config", headers=auth, json={"site_name": ""}).get_json()["site_name"] == "myMangaLib"

def test_owner_opens_registration_and_admins_see_waiting_users(client, auth):
    anonymous = client.application.test_client()
    assert client.get("/api/v1/server/info").get_json()["registration_open"] is False
    assert anonymous.post("/api/v1/auth/register", json={"username": "early", "password": PASSWORD}).status_code == 403

    client.put("/api/v1/server/config", headers=auth, json={"allow_new_users": True})
    assert client.get("/api/v1/server/info").get_json()["registration_open"] is True
    signup = anonymous.post("/api/v1/auth/register", json={"username": "waiting", "password": PASSWORD})
    assert signup.status_code == 201 and signup.get_json()["user"]["approved"] is False

    assert client.get("/api/v1/auth/me", headers=auth).get_json()["user"]["pending_users"] == 1
    assert login(client, "owner").get_json()["user"]["pending_users"] == 1

    client.put("/api/v1/server/config", headers=auth, json={"auto_approve_new_users": True})
    instant = anonymous.post("/api/v1/auth/register", json={"username": "instant", "password": PASSWORD})
    assert instant.get_json()["user"]["approved"] is True

def test_normal_users_dont_get_a_pending_count(client, reader):
    assert "pending_users" not in client.get("/api/v1/auth/me", headers=reader["headers"]).get_json()["user"]

def test_settings_survive_a_restart(app, client, auth, tmp_path):
    client.put("/api/v1/server/config", headers=auth, json={"allow_new_users": True, "hide_titles": True})
    from mymangalib import create_app
    restarted = create_app(str(tmp_path / "config.toml"))
    info = restarted.test_client().get("/api/v1/server/info").get_json()
    assert info["registration_open"] is True and info["hide_titles"] is True
    # Put the module-level switch back for the other tests
    client.put("/api/v1/server/config", headers=auth, json={"hide_titles": False})

def test_admins_reject_signups_by_deleting_them(app, client, auth, reader):
    app.config["ALLOW_NEW_USERS"] = True
    client.application.test_client().post("/api/v1/auth/register", json={"username": "spam", "password": PASSWORD})
    users = client.get("/api/v1/admin/users", headers=auth).get_json()["users"]
    spam = next(u for u in users if u["username"] == "spam")

    client.put(f"/api/v1/admin/users/{reader['id']}", headers=auth, json={"role": "admin"})
    # An admin can reject a sign-up but not delete an approved member
    assert client.delete(f"/api/v1/admin/users/{spam['id']}", headers=reader["headers"]).status_code == 200
    assert client.delete("/api/v1/admin/users/1", headers=reader["headers"]).status_code == 403
    assert login(client, "spam").status_code == 401

    # The owner can remove members, which signs them out
    assert client.delete(f"/api/v1/admin/users/{reader['id']}", headers=auth).status_code == 200
    assert client.get("/api/v1/auth/me", headers=reader["headers"]).status_code == 401

def test_classic_ui_switch_is_saved_too(app, client, auth, tmp_path):
    client.post("/login", data={"username": "owner", "password": PASSWORD})
    client.post("/api/settings/config", data={"hide-titles": "true"})
    assert client.get("/api/v1/server/config", headers=auth).get_json()["hide_titles"] is True
    client.put("/api/v1/server/config", headers=auth, json={"hide_titles": False})
