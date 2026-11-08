import io, json, os

import pytest

from conftest import PASSWORD, PNG, login
from mymangalib.server import feedback, logbuffer

def bearer(token):
    return {"Authorization": f"Bearer {token}"}

def make_user(client, auth, name, role=None):
    response = client.post("/api/v1/auth/register", headers=auth, json={"username": name, "password": PASSWORD})
    user_id = response.get_json()["user"]["id"]
    if role:
        client.put(f"/api/v1/admin/users/{user_id}", headers=auth, json={"role": role})
    return {"id": user_id, "headers": bearer(login(client, name).get_json()["token"])}

@pytest.fixture
def reader(client, auth):
    return make_user(client, auth, "reader")

@pytest.fixture
def admin(client, auth):
    return make_user(client, auth, "helper", role="admin")

def first_manga_id(client, auth):
    return client.get("/api/v1/manga?list=all", headers=auth).get_json()["items"][0]["id"]

def send(client, headers, data, screenshots=()):
    form = {"data": json.dumps(data)}
    if screenshots:
        form["screenshots"] = [(io.BytesIO(content), name) for name, content in screenshots]
    return client.post("/api/v1/feedback", headers=headers, data=form, content_type="multipart/form-data")

BUG = {"kind": "bug", "title": "Reader crashes", "body": "It closes", "steps": "1. Open\n2. Swipe",
       "client_log": "error at Reader.jsx Bearer abc123", "context": {"platform": "android", "app_version": "1.9.0"}}

def test_bug_with_screenshots_reaches_owner_only(client, auth, reader, admin):
    response = send(client, reader["headers"], BUG, [("one.png", PNG), ("two.png", PNG)])
    assert response.status_code == 201, response.get_json()
    item = response.get_json()["feedback"]
    assert item["status"] == "new" and len(item["attachments"]) == 2
    # The sender doesn't get device details or the server log back
    assert "context" not in item and "server_log" not in item
    assert "abc123" not in item["client_log"]

    # Owner sees it with everything
    inbox = client.get("/api/v1/admin/feedback", headers=auth).get_json()["feedback"]
    assert [i["id"] for i in inbox] == [item["id"]]
    detail = client.get(f"/api/v1/admin/feedback/{item['id']}", headers=auth).get_json()["feedback"]
    assert detail["context"]["platform"] == "android" and detail["context"]["server_version"]
    assert "server_log" in detail and "needs_info" in detail["allowed_statuses"]

    # The screenshot loads with ?t= (an <img> can't send headers)
    token = auth["Authorization"].split()[1]
    image = client.get(f"/api/v1{detail['attachments'][0]['url'].removeprefix('/api/v1')}?t={token}")
    assert image.status_code == 200 and image.data == PNG

    # Admins handle content, not bugs
    assert client.get("/api/v1/admin/feedback", headers=admin["headers"]).get_json()["feedback"] == []
    assert client.get(f"/api/v1/admin/feedback/{item['id']}", headers=admin["headers"]).status_code == 404
    assert client.get(f"/api/v1/feedback/{item['id']}", headers=admin["headers"]).status_code == 404

def test_admins_see_content_items(client, auth, reader, admin):
    manga_id = first_manga_id(client, auth)
    assert send(client, reader["headers"], {"kind": "content_request", "title": "Please add Gamma"}).status_code == 201
    response = send(client, reader["headers"], {"kind": "content_problem", "manga_id": manga_id, "chapter": 2,
                                                "body": "Page 3 is blank"}, [("p.png", PNG)])
    assert response.status_code == 201
    assert response.get_json()["feedback"]["title"].startswith("Problem with ")

    items = client.get("/api/v1/admin/feedback", headers=admin["headers"]).get_json()["feedback"]
    assert {i["kind"] for i in items} == {"content_request", "content_problem"}
    me = client.get("/api/v1/auth/me", headers=admin["headers"]).get_json()["user"]
    assert me["pending_feedback"] == 2

    item_id = items[0]["id"]
    detail = client.post(f"/api/v1/admin/feedback/{item_id}/status", headers=admin["headers"],
                         json={"status": "done", "note": "Added"}).get_json()["feedback"]
    assert detail["status"] == "done"
    # Content items never use the agent's statuses
    assert client.post(f"/api/v1/admin/feedback/{item_id}/status", headers=admin["headers"],
                       json={"status": "approved"}).status_code == 409

@pytest.mark.parametrize("data,files,message", [
    ({"kind": "nope", "title": "x"}, [], "kind"),
    ({"kind": "bug", "title": "x"}, [], "Body is required"),
    ({"kind": "bug", "title": "x", "body": "y"}, [("fake.png", b"not an image at all")], "PNG"),
    ({"kind": "bug", "title": "x", "body": "y"}, [("a.png", PNG)] * 4, "at most 3"),
    ({"kind": "bug", "title": "x", "body": "y"}, [("big.png", PNG + b"0" * feedback.MAX_SCREENSHOT_BYTES)], "MB"),
    ({"kind": "app_idea", "title": "x"}, [("a.png", PNG)], "only be added"),
    ({"kind": "content_problem", "manga_id": 9999}, [], "series"),
])
def test_rejects_bad_feedback(client, reader, data, files, message):
    response = send(client, reader["headers"], data, files)
    assert response.status_code == 400
    assert message in response.get_json()["error"]["message"]

def test_daily_limit(client, reader):
    for _ in range(feedback.MAX_PER_DAY):
        assert client.post("/api/v1/feedback", headers=reader["headers"],
                           json={"kind": "app_idea", "title": "Idea"}).status_code == 201
    response = client.post("/api/v1/feedback", headers=reader["headers"], json={"kind": "app_idea", "title": "One more"})
    assert response.status_code == 429

def test_needs_info_round_trip(client, auth, reader):
    item_id = send(client, reader["headers"], BUG).get_json()["feedback"]["id"]
    assert client.get("/api/v1/auth/me", headers=auth).get_json()["user"]["pending_feedback"] == 1

    client.post(f"/api/v1/admin/feedback/{item_id}/status", headers=auth,
                json={"status": "needs_info", "note": "Which phone?"})
    assert client.get("/api/v1/auth/me", headers=auth).get_json()["user"]["pending_feedback"] == 0
    # Can't withdraw once it's been looked at
    assert client.delete(f"/api/v1/feedback/{item_id}", headers=reader["headers"]).status_code == 403

    response = client.post(f"/api/v1/feedback/{item_id}/comments", headers=reader["headers"], json={"body": "A Galaxy S24"})
    item = response.get_json()["feedback"]
    assert item["status"] == "new"
    assert [e["kind"] for e in item["events"]] == ["status", "comment", "status"]
    assert item["events"][0]["body"] == "Which phone?"

    mine = client.get("/api/v1/feedback/mine", headers=reader["headers"]).get_json()["feedback"]
    assert [i["id"] for i in mine] == [item_id]

def test_invalid_transition_and_plan_decision(client, app, auth, reader):
    item_id = send(client, reader["headers"], {"kind": "server_idea", "title": "Webhooks"}).get_json()["feedback"]["id"]
    assert client.post(f"/api/v1/admin/feedback/{item_id}/status", headers=auth,
                       json={"status": "plan_ready"}).status_code == 409

    # What the agent worker will do: a plan, then the owner decides
    with app.app_context():
        item = feedback.db.session.get(feedback.Feedback, item_id)
        item.status = "plan_ready"
        feedback.add_event(item, "agent", "plan", "## Plan\nAdd webhooks")
        feedback.db.session.commit()
    detail = client.post(f"/api/v1/admin/feedback/{item_id}/status", headers=auth,
                         json={"status": "changes_requested", "note": "Smaller please"}).get_json()["feedback"]
    assert [e["kind"] for e in detail["events"]] == ["plan", "plan_decision", "status"]
    # The sender doesn't see the agent's plan
    events = client.get(f"/api/v1/feedback/{item_id}", headers=reader["headers"]).get_json()["feedback"]["events"]
    assert [e["kind"] for e in events] == ["status"]

def test_server_errors_go_into_bug_reports(client, app, reader):
    logbuffer.logger("server").error("Something broke for /api/v1/x?t=secret")
    item_id = send(client, reader["headers"], BUG).get_json()["feedback"]["id"]
    with app.app_context():
        server_log = feedback.db.session.get(feedback.Feedback, item_id).server_log
    assert "Something broke" in server_log and "secret" not in server_log

def test_unhandled_error_is_logged(client, app, auth, monkeypatch):
    def boom():
        raise RuntimeError("boom for the log")
    monkeypatch.setitem(app.view_functions, "api_v1.tags", boom)
    with pytest.raises(RuntimeError):
        client.get("/api/v1/tags", headers=auth)
    assert "boom for the log" in logbuffer.recent()

def test_deleting_feedback_user_and_manga(client, app, auth, reader):
    item_id = send(client, reader["headers"], BUG, [("a.png", PNG)]).get_json()["feedback"]["id"]
    manga_id = first_manga_id(client, auth)
    problem_id = send(client, auth, {"kind": "content_problem", "manga_id": manga_id}).get_json()["feedback"]["id"]
    with app.app_context():
        folder = os.path.join(feedback.feedback_dir(), str(item_id))
    assert os.path.isdir(folder)

    assert client.delete(f"/api/v1/admin/users/{reader['id']}", headers=auth).status_code == 200
    assert not os.path.exists(folder)
    assert client.get(f"/api/v1/admin/feedback/{item_id}", headers=auth).status_code == 404

    assert client.delete(f"/api/v1/manga/{manga_id}", headers=auth).status_code == 200
    detail = client.get(f"/api/v1/admin/feedback/{problem_id}", headers=auth).get_json()["feedback"]
    assert detail["manga_id"] is None and detail["manga_title"]

    assert client.delete(f"/api/v1/feedback/{problem_id}", headers=auth).status_code == 200
    assert client.get("/api/v1/admin/feedback?status=all", headers=auth).get_json()["feedback"] == []

def test_normal_users_have_no_inbox(client, reader):
    assert client.get("/api/v1/admin/feedback", headers=reader["headers"]).status_code == 403
