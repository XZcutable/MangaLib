import pytest

from conftest import PASSWORD, make_app, register

INDEX = "<!doctype html><title>myMangaLib app</title>"

@pytest.fixture
def client(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "assets" / "index-abc123.js").write_text("console.log('app')")
    app = make_app(tmp_path, f'FRONTEND_PATH="{dist.as_posix()}"')
    return app.test_client()

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
