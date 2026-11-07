import os

import pytest
from sqlalchemy import select

from conftest import PASSWORD, add_volume, make_app
from mymangalib.database import db, normalize_languages
from mymangalib.models import ContentTag, Manga, MangaMetadata
from mymangalib.server import languages, metadata
from mymangalib.server.search import Filter, parse

# --- Parsing ---

def test_parse_terms_and_phrases():
    parsed = parse('JoJo\'s  "Bizarre Adventure" -part -"stone ocean"')
    assert parsed.terms == [("JoJo's", False), ("Bizarre Adventure", False), ("part", True), ("stone ocean", True)]
    assert parsed.filters == []

def test_parse_filters():
    parsed = parse('tag:fantasy|action&"slice of life" -tag:romance nsfw: -nsfw language:english|japanese| is:unread')
    assert parsed.filters == [
        Filter("tag", False, [["fantasy"], ["action", "slice of life"]]),
        Filter("tag", True, [["romance"]]),
        Filter("nsfw", False, []),
        Filter("nsfw", True, []),
        Filter("language", False, [["english"], ["japanese"]]),
        Filter("is", False, [["unread"]]),
    ]
    assert parse("TAG:Fantasy&").filters == [Filter("tag", False, [["fantasy"]])]

def test_unknown_keys_and_unterminated_quotes_search_titles():
    assert parse("re:zero").terms == [("re:zero", False)]
    assert parse('"open phrase').terms == [("open phrase", False)]
    assert parse('tag:"slice of').filters == [Filter("tag", False, [["slice of"]])]
    assert parse("- -").terms == []

# --- Results ---

EXTRA = ["Café Été", "JoJo's Bizarre", "100% Done_Now", "Gamma Ray"]

@pytest.fixture
def app(tmp_path):
    for title in EXTRA:
        os.makedirs(tmp_path / "library" / title)
        add_volume(str(tmp_path / "library"), title, f"{title} v01.cbz")
    app = make_app(tmp_path)
    with app.app_context():
        def tag(name, nsfw=False):
            db.session.add(ContentTag(tag=name, nsfw=nsfw))
        for name in ("fantasy", "action", "slice of life"):
            tag(name)
        for name in ("gore", "ecchi"):
            tag(name, nsfw=True)
        db.session.flush()

        def setup(title, tags=(), language=""):
            manga = db.session.scalar(select(Manga).where(Manga.title == title))
            manga.manga_metadata.tags.extend(db.session.get(ContentTag, name) for name in tags)
            manga.manga_metadata.language = language

        setup("Alpha", ["fantasy", "action"], "en")
        setup("Beta", ["fantasy", "gore"], "ja")
        setup("Gamma Ray", ["slice of life"], "ko")
        setup("Café Été", ["ecchi"], "mul")
        db.session.commit()
    return app

def titles(client, auth, q):
    response = client.get("/api/v1/manga/search", query_string={"q": q, "limit": 100}, headers=auth)
    assert response.status_code == 200
    return sorted(item["title"] for item in response.get_json()["items"])

def test_title_search(client, auth):
    assert titles(client, auth, "ALPHA") == ["Alpha"]
    assert titles(client, auth, "café été") == ["Café Été"]
    assert titles(client, auth, "CAFÉ") == ["Café Été"]
    assert titles(client, auth, "jojo's") == ["JoJo's Bizarre"]
    assert titles(client, auth, '"ray gamma"') == []
    assert titles(client, auth, "ray gamma") == ["Gamma Ray"]
    assert titles(client, auth, "100%") == ["100% Done_Now"]
    assert titles(client, auth, "e_n") == ["100% Done_Now"]
    assert titles(client, auth, "a -beta -gamma -jojo -café -done") == ["Alpha"]

def test_tag_logic(client, auth):
    assert titles(client, auth, "tag:fantasy") == ["Alpha", "Beta"]
    assert titles(client, auth, "tag:fantasy&action") == ["Alpha"]
    assert titles(client, auth, 'tag:action|"slice of life"') == ["Alpha", "Gamma Ray"]
    assert titles(client, auth, 'tag:"slice of life"|fantasy&action') == ["Alpha", "Gamma Ray"]
    assert titles(client, auth, "-tag:fantasy|ecchi") == ["100% Done_Now", "Gamma Ray", "JoJo's Bizarre"]
    assert titles(client, auth, "-tag:fantasy&action tag:fantasy") == ["Beta"]
    assert len(titles(client, auth, "tag:")) == 6  # an empty filter is ignored

def test_nsfw(client, auth):
    assert titles(client, auth, "nsfw:") == ["Beta", "Café Été"]
    assert titles(client, auth, "nsfw:gore") == ["Beta"]
    assert titles(client, auth, "nsfw:fantasy") == []
    assert titles(client, auth, "tag:fantasy -nsfw") == ["Alpha"]
    assert titles(client, auth, "tag:fantasy -nsfw:") == ["Alpha"]
    assert titles(client, auth, "tag:fantasy -nsfw:gore") == ["Alpha"]

def test_language(client, auth):
    assert titles(client, auth, "language:english") == ["Alpha"]
    assert titles(client, auth, "language:English|japanese") == ["Alpha", "Beta"]
    assert titles(client, auth, "language:english&japanese") == ["Alpha", "Beta"]
    assert titles(client, auth, "language:mixed") == ["Café Été"]
    assert titles(client, auth, "-language:english|japanese|korean|mixed") == ["100% Done_Now", "JoJo's Bizarre"]
    assert titles(client, auth, "language:klingon") == []

def test_status(client, auth):
    alpha = client.get("/api/v1/manga/search?q=alpha", headers=auth).get_json()["items"][0]["id"]
    client.put(f"/api/v1/manga/{alpha}/state", headers=auth, json={"is_read": True})
    assert titles(client, auth, "is:read") == ["Alpha"]
    assert "Alpha" not in titles(client, auth, "is:unread")
    assert titles(client, auth, "is:tagged&unread") == ["Beta", "Café Été", "Gamma Ray"]
    assert titles(client, auth, "is:untagged") == ["100% Done_Now", "JoJo's Bizarre"]

def test_classic_search_uses_the_same_language(client, auth):
    client.post("/login", data={"username": "owner", "password": PASSWORD})
    found = client.get("/api/fetch-search", query_string={"q": "tag:fantasy|action -nsfw"}).get_json()
    assert [item["title"] for item in found] == ["Alpha"]
    assert client.get("/manga/search", query_string={"q": "tag:a&b"}).status_code == 200

# --- Languages ---

def test_normalize_language():
    assert languages.normalize("English") == "en"
    assert languages.normalize("en-US") == "en"
    assert languages.normalize("jp") == "ja"
    assert languages.normalize("zh_TW") == "zh"
    assert languages.normalize("Multi") == "mul"
    assert languages.normalize("pt-BR") == "pt-BR"
    assert languages.normalize("  ") is None

def test_language_edits_must_be_a_known_code():
    assert metadata.clean({"language": "ai"}) == ({"language": "ai"}, None)
    assert metadata.clean({"language": ""}) == ({"language": None}, None)
    assert metadata.clean({"language": "English"})[1] is not None

def test_startup_normalizes_stored_languages(app):
    with app.app_context():
        metas = db.session.scalars(select(MangaMetadata).order_by(MangaMetadata.manga_id)).all()
        metas[0].language, metas[1].language = "Japanese", "Elvish"
        db.session.commit()
        normalize_languages()
        assert [metas[0].language, metas[1].language] == ["ja", "Elvish"]

def test_server_info_lists_languages(client):
    names = [language["name"] for language in client.get("/api/v1/server/info").get_json()["languages"]]
    assert names == ["English", "Japanese", "Korean", "Chinese", "Spanish", "AI Translated", "Mixed"]
