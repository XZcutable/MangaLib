from conftest import PNG, PASSWORD, register, login

def manga_id_by_title(client, auth, title):
    items = client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"]
    return next(item["id"] for item in items if item["title"] == title)

# --- Auth ---

def test_server_info_is_public_and_reports_setup(client):
    info = client.get("/api/v1/server/info").get_json()
    assert info["api_version"] == 1
    assert info["needs_setup"] is True
    assert info["registration_open"] is True

def test_first_user_is_owner_then_registration_closes(client):
    response = register(client, "owner")
    assert response.status_code == 201
    assert response.get_json()["user"]["is_owner"] is True

    response = register(client, "someone")
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "registration_closed"

def test_login_returns_token_for_me(client):
    register(client, "owner")
    assert login(client, "owner", "wrong").status_code == 401
    assert login(client, "nobody").status_code == 401

    token = login(client, "owner").get_json()["token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.get_json()["user"]["username"] == "owner"

def test_unapproved_user_cannot_log_in(app, client, auth):
    # The owner (an admin) can add users. Those are approved, so make one that isn't.
    app.config["ALLOW_NEW_USERS"] = True
    anonymous = app.test_client()
    assert register(anonymous, "pending").status_code == 201
    response = login(anonymous, "pending")
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "not_approved"

def test_missing_or_bad_token_is_json_401_not_redirect(client, auth):
    for headers in ({}, {"Authorization": "Bearer not-a-token"}):
        response = client.get("/api/v1/manga", headers=headers)
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "unauthorized"

def test_session_cookie_does_not_authenticate_api_v1(client):
    register(client, "owner")
    client.post("/login", data={"username": "owner", "password": PASSWORD})
    assert client.get("/api/v1/auth/me").status_code == 401

def test_unknown_route_is_json_404(client, auth):
    response = client.get("/api/v1/nope", headers=auth)
    assert response.status_code == 404
    assert "error" in response.get_json()

def test_logout_revokes_token(client, auth):
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401

def test_tokens_can_be_listed_and_revoked(client, auth):
    second = login(client, "owner").get_json()["token"]
    listed = client.get("/api/v1/auth/tokens", headers=auth).get_json()["tokens"]
    assert len(listed) == 2
    other = next(token for token in listed if not token["current"])
    assert client.delete(f"/api/v1/auth/tokens/{other['id']}", headers=auth).status_code == 200
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {second}"}).status_code == 401

# --- Library ---

def test_list_shape_and_paging(client, auth):
    body = client.get("/api/v1/manga?list=all&limit=1", headers=auth).get_json()
    assert body["total"] == 2
    assert body["next_offset"] == 1
    item = body["items"][0]
    assert item["title"] == "Alpha"
    assert item["total_chapters"] == 2
    assert item["cover_url"] == f"/api/v1/manga/{item['id']}/cover"
    assert item["progress"] == 0.0

    body = client.get("/api/v1/manga?list=all&limit=1&offset=1", headers=auth).get_json()
    assert body["items"][0]["title"] == "Beta"
    assert body["next_offset"] is None

    latest = client.get("/api/v1/manga?list=latest", headers=auth).get_json()["items"]
    assert [item["title"] for item in latest] == ["Beta", "Alpha"]

    assert client.get("/api/v1/manga?list=bogus", headers=auth).status_code == 400

def test_unread_and_random_lists(client, auth):
    alpha = manga_id_by_title(client, auth, "Alpha")
    client.put(f"/api/v1/manga/{alpha}/state", headers=auth, json={"is_read": True})
    unread = client.get("/api/v1/manga?list=unread", headers=auth).get_json()
    assert [item["title"] for item in unread["items"]] == ["Beta"]
    shuffled = client.get("/api/v1/manga?list=random", headers=auth).get_json()
    assert sorted(item["title"] for item in shuffled["items"]) == ["Alpha", "Beta"]

def test_manga_info_and_chapter(client, auth):
    alpha = manga_id_by_title(client, auth, "Alpha")
    info = client.get(f"/api/v1/manga/{alpha}", headers=auth).get_json()
    assert [chapter["page_count"] for chapter in info["chapters"]] == [3, 3]
    assert info["resume"] == {"chapter": 1, "page": 1}

    chapter = client.get(f"/api/v1/manga/{alpha}/chapters/1", headers=auth).get_json()
    assert chapter["page_count"] == 3
    assert chapter["previous_chapter"] is None and chapter["next_chapter"] == 2
    assert chapter["pages"][0]["image_url"] == f"/api/v1/manga/{alpha}/chapters/1/pages/1/image"

    assert client.get(f"/api/v1/manga/{alpha}/chapters/9", headers=auth).status_code == 404
    assert client.get("/api/v1/manga/999", headers=auth).status_code == 404

def test_images_accept_header_or_query_token(client, auth, owner_token):
    alpha = manga_id_by_title(client, auth, "Alpha")
    beta = manga_id_by_title(client, auth, "Beta")

    cover = client.get(f"/api/v1/manga/{alpha}/cover", headers=auth)
    assert cover.status_code == 200 and cover.mimetype == "image/jpeg" and cover.data[:2] == bytes([0xFF, 0xD8])
    assert client.get(f"/api/v1/manga/{alpha}/cover?full=1", headers=auth).data == PNG
    assert client.get(f"/api/v1/manga/{alpha}/chapters/2/pages/3/image?t={owner_token}").data == PNG
    assert client.get(f"/api/v1/manga/{beta}/chapters/1/pages/2/image?t={owner_token}").data == PNG
    assert client.get(f"/api/v1/manga/{alpha}/cover").status_code == 401

def test_query_token_only_works_for_images(client, auth, owner_token):
    assert client.get(f"/api/v1/auth/me?t={owner_token}").status_code == 401

def test_progress_persists_and_last_page_marks_read(client, auth):
    alpha = manga_id_by_title(client, auth, "Alpha")
    response = client.put(f"/api/v1/manga/{alpha}/progress", headers=auth, json={"chapter": 1, "page": 3})
    assert response.status_code == 200

    info = client.get(f"/api/v1/manga/{alpha}", headers=auth).get_json()
    assert info["resume"] == {"chapter": 1, "page": 3}
    assert info["progress"] == 0.5

    history = client.get("/api/v1/manga?list=history", headers=auth).get_json()["items"]
    assert [item["id"] for item in history] == [alpha]

    client.put(f"/api/v1/manga/{alpha}/progress", headers=auth, json={"chapter": 2, "page": 3})
    info = client.get(f"/api/v1/manga/{alpha}", headers=auth).get_json()
    assert info["user"]["is_read"] is True
    assert info["progress"] == 1.0

    bad = client.put(f"/api/v1/manga/{alpha}/progress", headers=auth, json={"chapter": 1, "page": 99})
    assert bad.status_code == 404
    bad = client.put(f"/api/v1/manga/{alpha}/progress", headers=auth, json={"chapter": "1"})
    assert bad.status_code == 400

def test_state_toggles_feed_lists(client, auth):
    beta = manga_id_by_title(client, auth, "Beta")
    user = client.put(f"/api/v1/manga/{beta}/state", headers=auth, json={"is_favorite": True, "is_queued": True}).get_json()["user"]
    assert user["is_favorite"] and user["is_queued"] and not user["is_read"]

    assert [i["id"] for i in client.get("/api/v1/manga?list=favorites", headers=auth).get_json()["items"]] == [beta]
    assert [i["id"] for i in client.get("/api/v1/manga?list=queued", headers=auth).get_json()["items"]] == [beta]

    client.put(f"/api/v1/manga/{beta}/state", headers=auth, json={"is_favorite": False})
    assert client.get("/api/v1/manga?list=favorites", headers=auth).get_json()["items"] == []
    assert client.get("/api/v1/manga?list=queued", headers=auth).get_json()["total"] == 1

def test_search_and_random(client, auth):
    results = client.get("/api/v1/manga/search?q=alpha", headers=auth).get_json()
    assert [item["title"] for item in results["items"]] == ["Alpha"]
    assert client.get("/api/v1/manga/search?q=", headers=auth).get_json()["total"] == 0

    alpha = manga_id_by_title(client, auth, "Alpha")
    client.put(f"/api/v1/manga/{alpha}/state", headers=auth, json={"is_read": True})
    beta = manga_id_by_title(client, auth, "Beta")
    for _ in range(5):
        assert client.get("/api/v1/manga/random?unread=1", headers=auth).get_json()["id"] == beta

def test_tags(client, auth):
    assert client.get("/api/v1/tags", headers=auth).get_json() == {"tags": []}

# --- CORS ---

def test_cors_preflight_for_app_origin(client):
    response = client.options("/api/v1/manga", headers={
        "Origin": "capacitor://localhost",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization",
    })
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "capacitor://localhost"

def test_cors_rejects_unknown_origin(client):
    response = client.get("/api/v1/server/info", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers

def test_cors_headers_on_401_so_app_can_read_it(client):
    response = client.get("/api/v1/manga", headers={"Origin": "https://localhost"})
    assert response.status_code == 401
    assert response.headers["Access-Control-Allow-Origin"] == "https://localhost"

# --- Old UI keeps working ---

def test_old_cookie_login_and_api(client):
    register(client, "owner")
    response = client.post("/login", data={"username": "owner", "password": PASSWORD})
    assert response.status_code == 302

    titles = client.get("/api/fetch-titles?sort=asc").get_json()
    assert [title["title"] for title in titles] == ["Alpha", "Beta"]

    alpha = titles[0]["id"]
    assert client.post("/api/user/manga/progress", data={"manga_id": alpha, "chapter_number": 1, "page_number": 2}).status_code == 200
    assert [t["id"] for t in client.get("/api/fetch-history").get_json()] == [alpha]
    fav = client.post(f"/api/user/manga/favorite?manga_id={alpha}", data={"is_fav": "true"}).get_json()
    assert fav["is_favorite"] is True
    assert client.get("/api/fetch-search?q=beta").get_json()[0]["title"] == "Beta"
    assert client.get("/manga/all").status_code == 200

def test_old_api_still_redirects_when_logged_out(client):
    register(client, "owner")
    assert client.get("/api/fetch-titles").status_code == 302

def test_old_register_page_creates_owner(client):
    response = client.post("/register", data={"username": "boss", "password": PASSWORD})
    assert response.status_code == 302
    assert client.post("/login", data={"username": "boss", "password": PASSWORD}).status_code == 302
