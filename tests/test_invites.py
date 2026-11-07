from datetime import datetime, timedelta, timezone

import pytest

from conftest import PASSWORD, login, make_app, register
from mymangalib.database import db
from mymangalib.models import Invite, User

def bearer(token):
    return {"Authorization": f"Bearer {token}"}

def make_user(client, auth, username, role=None):
    """An approved account (created by the owner), optionally given a role. Returns its auth header."""
    user = client.post("/api/v1/auth/register", headers=auth, json={"username": username, "password": PASSWORD}).get_json()["user"]
    if role:
        client.put(f"/api/v1/admin/users/{user['id']}", headers=auth, json={"role": role})
    return bearer(login(client, username).get_json()["token"])

def invite(client, headers, **body):
    response = client.post("/api/v1/invites", headers=headers, json=body)
    assert response.status_code == 201, response.get_json()
    return response.get_json()

def join(client, code, username):
    """Registers without logging in, the way a new person on the join page does."""
    return client.application.test_client().post(
        "/api/v1/auth/register", json={"username": username, "password": PASSWORD, "invite": code})

def set_registration(client, auth, open_, auto_approve=False):
    client.put("/api/v1/server/config", headers=auth, json={"allow_new_users": open_, "auto_approve_new_users": auto_approve})

# --- Admin invites ---

def test_admin_invite_works_while_registration_is_closed(app, client, auth):
    created = invite(client, auth)
    assert created["invite"]["approved_on_join"] is True and created["invite"]["status"] == "active"

    # Closed for everyone else
    assert register(client.application.test_client(), "stranger").status_code == 403

    response = join(client, created["code"], "friend")
    assert response.status_code == 201
    user = response.get_json()["user"]
    assert user["approved"] is True
    assert login(client, "friend").status_code == 200
    with app.app_context():
        assert db.session.get(User, user["id"]).invited_by == 1

def test_invites_are_used_up(client, auth):
    code = invite(client, auth)["code"]
    assert join(client, code, "first").status_code == 201
    response = join(client, code, "second")
    assert response.status_code == 403 and response.get_json()["error"]["code"] == "invite_used_up"

def test_invites_with_several_uses_and_unlimited(client, auth):
    code = invite(client, auth, max_uses=2)["code"]
    assert join(client, code, "a").status_code == 201
    assert join(client, code, "b").status_code == 201
    assert join(client, code, "c").status_code == 403

    unlimited = invite(client, auth, max_uses=None)
    assert unlimited["invite"]["max_uses"] is None
    for name in ("d", "e", "f"):
        assert join(client, unlimited["code"], name).status_code == 201

def test_a_taken_username_doesnt_use_up_the_invite(client, auth):
    code = invite(client, auth)["code"]
    assert join(client, code, "owner").status_code == 409
    assert join(client, code, "newcomer").status_code == 201

def test_expired_and_unknown_invites(app, client, auth):
    created = invite(client, auth)
    with app.app_context():
        row = db.session.get(Invite, created["invite"]["id"])
        row.expires = str(datetime.now(timezone.utc) - timedelta(minutes=1))
        db.session.commit()
    response = join(client, created["code"], "late")
    assert response.status_code == 403 and response.get_json()["error"]["code"] == "invite_expired"

    response = join(client, "not-a-real-code", "guess")
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "invite_invalid"

def test_demoted_admins_invites_follow_the_normal_rules(client, auth):
    admin = make_user(client, auth, "helper", role="admin")
    code = invite(client, admin)["code"]
    helper_id = next(u["id"] for u in client.get("/api/v1/admin/users", headers=auth).get_json()["users"] if u["username"] == "helper")
    client.put(f"/api/v1/admin/users/{helper_id}", headers=auth, json={"role": "user"})

    response = join(client, code, "late")
    assert response.status_code == 403 and response.get_json()["error"]["code"] == "registration_closed"

# --- User invites ---

def test_users_can_only_invite_while_registration_is_open(client, auth):
    reader = make_user(client, auth, "reader")
    assert client.get("/api/v1/auth/me", headers=reader).get_json()["user"]["can_invite"] is False
    response = client.post("/api/v1/invites", headers=reader, json={})
    assert response.status_code == 403 and response.get_json()["error"]["code"] == "registration_closed"

    set_registration(client, auth, True)
    assert client.get("/api/v1/auth/me", headers=reader).get_json()["user"]["can_invite"] is True
    created = invite(client, reader)
    assert created["invite"]["approved_on_join"] is False

    # Without auto-approve the new account waits for an admin, like any sign-up
    response = join(client, created["code"], "friend")
    assert response.status_code == 201 and response.get_json()["user"]["approved"] is False

def test_user_invites_follow_auto_approve(client, auth):
    reader = make_user(client, auth, "reader")
    set_registration(client, auth, True, auto_approve=True)
    code = invite(client, reader)["code"]
    assert join(client, code, "friend").get_json()["user"]["approved"] is True

def test_user_invites_stop_working_when_registration_closes(client, auth):
    reader = make_user(client, auth, "reader")
    set_registration(client, auth, True)
    code = invite(client, reader)["code"]
    set_registration(client, auth, False)

    info = client.get(f"/api/v1/invites/{code}").get_json()
    assert info["valid"] is False and info["status"] == "registration_closed"
    assert join(client, code, "friend").status_code == 403

# --- Listing, info and deleting ---

def test_invite_info_is_public(client, auth):
    client.put("/api/v1/server/config", headers=auth, json={"site_name": "Home Manga"})
    code = invite(client, auth)["code"]
    response = client.application.test_client().get(f"/api/v1/invites/{code}")
    assert response.status_code == 200
    info = response.get_json()
    assert info["valid"] is True and info["site_name"] == "Home Manga"
    assert info["invited_by"] == "owner" and info["approved_on_join"] is True
    # The code itself is never sent back
    assert code not in response.get_data(as_text=True)

    assert client.get("/api/v1/invites/nope").status_code == 404

def test_users_see_and_delete_only_their_own(client, auth):
    set_registration(client, auth, True)
    reader = make_user(client, auth, "reader")
    other = make_user(client, auth, "other")
    mine = invite(client, reader)["invite"]
    theirs = invite(client, other)["invite"]
    owners = invite(client, auth)["invite"]

    assert [i["id"] for i in client.get("/api/v1/invites", headers=reader).get_json()["invites"]] == [mine["id"]]
    assert {i["id"] for i in client.get("/api/v1/invites", headers=auth).get_json()["invites"]} == {mine["id"], theirs["id"], owners["id"]}

    assert client.delete(f"/api/v1/invites/{theirs['id']}", headers=reader).status_code == 404
    assert client.delete(f"/api/v1/invites/{mine['id']}", headers=reader).status_code == 200
    # Admins can cancel anyone's
    assert client.delete(f"/api/v1/invites/{theirs['id']}", headers=auth).status_code == 200
    assert [i["id"] for i in client.get("/api/v1/invites", headers=auth).get_json()["invites"]] == [owners["id"]]

def test_deleted_invite_stops_working(client, auth):
    created = invite(client, auth)
    client.delete(f"/api/v1/invites/{created['invite']['id']}", headers=auth)
    assert join(client, created["code"], "friend").status_code == 404

def test_deleting_a_user_deletes_their_invites(app, client, auth):
    set_registration(client, auth, True)
    reader = make_user(client, auth, "reader")
    invite(client, reader)
    reader_id = client.get("/api/v1/auth/me", headers=reader).get_json()["user"]["id"]
    assert client.delete(f"/api/v1/admin/users/{reader_id}", headers=auth).status_code == 200
    with app.app_context():
        assert db.session.query(Invite).count() == 0

@pytest.mark.parametrize("body", [
    {"expires_days": 0}, {"expires_days": 31}, {"expires_days": "7"}, {"expires_days": True},
    {"max_uses": 0}, {"max_uses": 101}, {"max_uses": 1.5},
])
def test_invite_limits_are_checked(client, auth, body):
    assert client.post("/api/v1/invites", headers=auth, json=body).status_code == 400

def test_invites_need_a_login(client):
    assert client.post("/api/v1/invites", json={}).status_code == 401
    assert client.get("/api/v1/invites").status_code == 401

# --- Public address ---

def test_owner_sets_the_public_address(client, auth):
    assert client.get("/api/v1/server/info").get_json()["public_url"] == ""
    response = client.put("/api/v1/server/config", headers=auth, json={"public_url": " https://manga.example.com/ "})
    assert response.get_json()["public_url"] == "https://manga.example.com"
    assert client.get("/api/v1/server/info").get_json()["public_url"] == "https://manga.example.com"

    for bad in ("manga.example.com", "ftp://x", "https://", "https://a b"):
        assert client.put("/api/v1/server/config", headers=auth, json={"public_url": bad}).status_code == 400
    assert client.put("/api/v1/server/config", headers=auth, json={"public_url": ""}).get_json()["public_url"] == ""

# --- Classic UI ---

def test_classic_join_link_goes_to_register_with_the_invite(client, auth):
    code = invite(client, auth)["code"]
    visitor = client.application.test_client()
    response = visitor.get(f"/join?code={code}")
    assert response.status_code == 302 and f"/register?invite={code}" in response.headers["Location"]

    page = visitor.get(f"/register?invite={code}").get_data(as_text=True)
    assert "Registration is Closed" not in page and 'name="username"' in page

    response = visitor.post(f"/register?invite={code}", data={"username": "classic", "password": PASSWORD})
    assert response.status_code == 302 and "/login" in response.headers["Location"]
    assert login(client, "classic").status_code == 200

def test_classic_register_rejects_a_bad_invite(client, auth):
    page = client.application.test_client().get("/register?invite=nope").get_data(as_text=True)
    assert "Registration is Closed" in page and "invite link isn" in page
