import pytest

from conftest import PASSWORD, make_app, register

INDEX = '<!doctype html><html><head><base href="/" /><title>myMangaLib app</title></head></html>'

MANIFEST = '{"name": "myMangaLib", "short_name": "myMangaLib", "start_url": "./", "scope": "./"}'

def frontend_app(tmp_path, extra_config: str = ""):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "assets" / "index-abc123.js").write_text("console.log('app')")
    (dist / "manifest.webmanifest").write_text(MANIFEST)
    (dist / "sw.js").write_text("self.addEventListener('fetch', () => {})")
    return make_app(tmp_path, f'FRONTEND_PATH="{dist.as_posix()}"\n{extra_config}')

@pytest.fixture
def client(tmp_path):
    return frontend_app(tmp_path).test_client()

@pytest.mark.parametrize("path", ["/", "/latest", "/manga/1", "/read/1/1/1", "/settings", "/connect"])
def test_app_pages_get_the_front_end(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.get_data(as_text=True) == INDEX
    assert response.headers["Cache-Control"] == "no-cache"

def test_assets_are_cached_long_term(client):
    response = client.get("/assets/index-abc123.js")
    assert response.get_data(as_text=True) == "console.log('app')"
    assert "max-age=31536000" in response.headers["Cache-Control"]

def test_index_html_itself_gets_the_base_tag(client):
    # The service worker stores this copy to open the app offline
    response = client.get("/index.html")
    assert response.get_data(as_text=True) == INDEX
    assert response.headers["Cache-Control"] == "no-cache"

def test_service_worker_is_not_cached(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "max-age=0" in response.headers["Cache-Control"] or "no-cache" in response.headers["Cache-Control"]

def test_manifest_has_the_site_name(tmp_path):
    client = frontend_app(tmp_path, "SITE_NAME='Home Shelf'").test_client()
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/manifest+json")
    assert response.headers["Cache-Control"] == "no-cache"
    manifest = response.get_json(force=True)
    assert manifest["name"] == "Home Shelf" and manifest["short_name"] == "Home Shelf"
    assert manifest["start_url"] == "./"

def test_files_outside_the_build_are_not_served(client):
    for path in ("/../config.toml", "/assets/../../config.toml", "/assets/..%2f..%2fconfig.toml", "/..%5cconfig.toml"):
        assert "SECRET_KEY" not in client.get(path).get_data(as_text=True)

def test_api_still_answers(client):
    info = client.get("/api/v1/server/info").get_json()
    assert info["name"] == "myMangaLib" and info["classic_ui_path"] == "/classic/"

def test_classic_ui_moves_under_classic(client):
    register(client, "owner")
    response = client.post("/classic/login", data={"username": "owner", "password": PASSWORD})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/classic/")  # Not the new UI's home

    page = client.get("/classic/manga/all")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'href="/classic/manga/' in html or "/classic/" in html
    assert client.get("/classic/settings").status_code == 200
    # Classic pages load their CSS from /static, which still works
    assert client.get("/static/assets/css/style.css").status_code == 200

def test_classic_redirects_stay_under_classic(client):
    response = client.get("/classic/manga/all")
    assert response.status_code == 302
    assert "/classic/" in response.headers["Location"]

# --- Under a sub-path behind a reverse proxy (https://example.com/manga/) ---

def check_sub_path(client, prefix: str, headers: dict):
    """The new UI, its files, the API, image URLs and the classic UI all work below the prefix."""
    page = client.get(f"{prefix}/read/1/1/1", headers=headers).get_data(as_text=True)
    assert '<base href="/manga/" />' in page and page.count("<base") == 1
    assert client.get(f"{prefix}/assets/index-abc123.js", headers=headers).status_code == 200
    assert '<base href="/manga/" />' in client.get(f"{prefix}/index.html", headers=headers).get_data(as_text=True)
    assert client.get(f"{prefix}/manifest.webmanifest", headers=headers).get_json(force=True)["scope"] == "./"

    register(client, "owner")
    token = client.post(f"{prefix}/api/v1/auth/login", headers=headers,
                        json={"username": "owner", "password": PASSWORD}).get_json()["token"]
    auth = {**headers, "Authorization": f"Bearer {token}"}
    cover_url = client.get(f"{prefix}/api/v1/manga?list=all", headers=auth).get_json()["items"][0]["cover_url"]
    # Relative to the server's base: the app adds https://example.com/manga in front
    assert cover_url.startswith("/api/v1/")
    assert client.get(f"{prefix}{cover_url}", headers=auth).status_code == 200

    classic = client.get(f"{prefix}/classic/login", headers=headers).get_data(as_text=True)
    assert 'href="/manga/classic/static/assets/css/style.css"' in classic
    assert client.get(f"{prefix}/classic/static/assets/css/style.css", headers=headers).status_code == 200

def test_url_prefix_for_a_proxy_that_keeps_the_path(tmp_path):
    client = frontend_app(tmp_path, "URL_PREFIX='/manga/'").test_client()
    check_sub_path(client, "/manga", {})
    # Still reachable directly at the root, e.g. from the local network
    assert '<base href="/" />' in client.get("/").get_data(as_text=True)

def test_forwarded_prefix_for_a_proxy_that_removes_the_path(tmp_path):
    client = frontend_app(tmp_path, "BEHIND_PROXY=true").test_client()
    check_sub_path(client, "", {"X-Forwarded-Prefix": "/manga"})

def test_at_the_root_the_base_is_slash(client):
    assert client.get("/settings").get_data(as_text=True) == INDEX
