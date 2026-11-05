import hashlib, io, json, os, re, sys, tarfile, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from conftest import make_app, register, login
from mymangalib import cli
from mymangalib.server import updater
from mymangalib.supervisor import MaintenanceServer, Supervisor, MAINTENANCE_HEADER
from mymangalib.update_files import Layout, RESTART_EXIT_CODE
from mymangalib.version import __version__, is_newer, parse

ROOT = Path(__file__).resolve().parent.parent
NEXT = "{}.{}.{}".format(*parse(__version__)[:2], parse(__version__)[2] + 1)


def make_bundle(version: str, requirements: str = "Flask\n", protocol: int = 1) -> bytes:
    files = {
        "manifest.json": json.dumps({"version": version, "protocol": protocol}),
        "pyproject.toml": f'[project]\nname = "mymangalib"\nversion = "{version}"\n',
        "requirements.txt": requirements,
        "mymangalib/__init__.py": "",
        "frontend/index.html": "<base href=\"/\">",
    }
    padding = os.urandom(6000)  # Doesn't compress, so the download takes several chunks
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        info = tarfile.TarInfo("mymangalib/padding.bin")
        info.size = len(padding)
        archive.addfile(info, io.BytesIO(padding))
    return buffer.getvalue()


class FakeGitHub:
    """Serves releases/latest and the bundle, with Range support, and records the ranges asked for."""

    def __init__(self, version: str, bundle: bytes, digest: str | None = None):
        self.version, self.bundle = version, bundle
        self.digest = digest or hashlib.sha256(bundle).hexdigest()
        self.ranges = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/latest":
                    body = json.dumps(fake.release()).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                match = re.match(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
                start, end = (int(match.group(1)), int(match.group(2))) if match else (0, len(fake.bundle) - 1)
                fake.ranges.append((start, end))
                body = fake.bundle[start:end + 1]
                self.send_response(206 if match else 200)
                self.send_header("Content-Length", str(len(body)))
                if match:
                    self.send_header("Content-Range", f"bytes {start}-{start + len(body) - 1}/{len(fake.bundle)}")
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def release(self):
        name = f"mymangalib-server-{self.version}.tar.gz"
        return {
            "tag_name": f"v{self.version}", "body": "Fixes", "html_url": "https://example.com/release",
            "published_at": "2026-11-04T00:00:00Z",
            "assets": [{"name": name, "size": len(self.bundle), "digest": f"sha256:{self.digest}",
                        "browser_download_url": f"{self.url}/{name}"}],
        }

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def github():
    fake = FakeGitHub(NEXT, make_bundle(NEXT))
    yield fake
    fake.close()


def update_app(tmp_path, github, extra=""):
    app = make_app(tmp_path, f'UPDATE_URL="{github.url}/latest"\nUPDATE_CHUNK_SIZE=1000\nUPDATE_CHUNK_PAUSE=0\n{extra}')
    return app


def owner(app):
    client = app.test_client()
    register(client, "owner")
    token = login(client, "owner").get_json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_versions_match():
    package = json.loads((ROOT / "manga-site" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == __version__
    assert is_newer("1.10.0", "1.9.9") and not is_newer("v1.2.0", "1.2.0")


def test_check_downloads_in_chunks_and_stages(tmp_path, github):
    app = update_app(tmp_path, github)
    client, auth = owner(app)

    update = client.post("/api/v1/admin/server/update/check", headers=auth).get_json()["update"]
    assert update["status"] == "ready" and update["staged_version"] == NEXT
    assert update["latest"]["version"] == NEXT and update["latest"]["notes"] == "Fixes"
    # Downloaded in 1000-byte ranges
    assert len(github.ranges) > 1 and all(end - start == 999 for start, end in github.ranges[:-1])

    layout = Layout(app.config["UPDATE_PATH"])
    assert layout.has_version(NEXT)
    assert not os.listdir(layout.downloads)  # The bundle is removed once unpacked
    # The owner's account shows it for the badge
    me = client.get("/api/v1/auth/me", headers=auth).get_json()["user"]
    assert me["server_update"] == {"status": "ready", "version": NEXT}


def test_download_resumes(tmp_path, github):
    app = update_app(tmp_path, github, "AUTO_UPDATE=false")
    client, auth = owner(app)
    assert client.post("/api/v1/admin/server/update/check", headers=auth).get_json()["update"]["status"] == "available"

    layout = Layout(app.config["UPDATE_PATH"])
    os.makedirs(layout.downloads)
    Path(layout.downloads, f"mymangalib-server-{NEXT}.tar.gz.part").write_bytes(github.bundle[:2500])
    update = client.post("/api/v1/admin/server/update/download", headers=auth).get_json()["update"]
    assert update["status"] == "ready"
    assert github.ranges[0][0] == 2500


def test_damaged_download_fails(tmp_path):
    github = FakeGitHub(NEXT, make_bundle(NEXT), digest="0" * 64)
    try:
        app = update_app(tmp_path, github)
        client, auth = owner(app)
        update = client.post("/api/v1/admin/server/update/check", headers=auth).get_json()["update"]
        assert update["status"] == "failed" and "checksum" in update["error"]
        assert not os.listdir(Layout(app.config["UPDATE_PATH"]).downloads)
    finally:
        github.close()


def test_bundle_for_newer_supervisor_needs_image(tmp_path):
    github = FakeGitHub(NEXT, make_bundle(NEXT, protocol=99))
    try:
        app = update_app(tmp_path, github)
        client, auth = owner(app)
        update = client.post("/api/v1/admin/server/update/check", headers=auth).get_json()["update"]
        assert update["status"] == "needs_image" and "docker compose pull" in update["error"]
    finally:
        github.close()


def test_up_to_date(tmp_path):
    github = FakeGitHub(__version__, make_bundle(__version__))
    try:
        app = update_app(tmp_path, github)
        client, auth = owner(app)
        update = client.post("/api/v1/admin/server/update/check", headers=auth).get_json()["update"]
        assert update["status"] == "idle" and update["latest"] is None and update["last_check"]
    finally:
        github.close()


def test_apply_backs_up_and_restarts(tmp_path, github):
    restarts = []
    app = update_app(tmp_path, github, "UPDATE_RESTART_DELAY=0")
    app.config["UPDATE_RESTART"] = lambda: restarts.append(True)
    client, auth = owner(app)
    client.post("/api/v1/admin/server/update/check", headers=auth)

    # Not under the supervisor: it can't restart itself
    response = client.post("/api/v1/admin/server/update/apply", headers=auth)
    assert response.status_code == 409 and "mymangalib serve" in response.get_json()["error"]["message"]

    app.config["UPDATE_ASSUME_SUPERVISED"] = True
    update = client.post("/api/v1/admin/server/update/apply", headers=auth).get_json()["update"]
    assert update["status"] == "applying"
    time.sleep(0.2)
    assert restarts == [True]

    layout = Layout(app.config["UPDATE_PATH"])
    assert layout.read_current() == NEXT
    pending = layout.read_json(layout.apply_file)
    assert pending["version"] == NEXT and pending["previous"] is None and os.path.isfile(pending["backup"])


def test_owner_only(tmp_path, github):
    app = update_app(tmp_path, github, "ALLOW_NEW_USERS=true\nAUTO_APPROVE_NEW_USERS=true")
    client, auth = owner(app)
    register(client, "reader")
    token = login(client, "reader").get_json()["token"]
    response = client.get("/api/v1/admin/server/update", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_no_auto_update_locks_the_switch(tmp_path, github):
    app = update_app(tmp_path, github, "AUTO_UPDATE=false")
    client, auth = owner(app)
    config = client.get("/api/v1/server/config", headers=auth).get_json()
    assert config["auto_update"] is False and config["auto_update_locked"] is True
    response = client.put("/api/v1/server/config", headers=auth, json={"auto_update": True})
    assert response.status_code == 409
    # The owner can still check by hand; it doesn't download on its own
    update = client.post("/api/v1/admin/server/update/check", headers=auth).get_json()["update"]
    assert update["status"] == "available" and not github.ranges


def test_owner_turns_auto_update_off(tmp_path, github):
    app = update_app(tmp_path, github)
    client, auth = owner(app)
    config = client.put("/api/v1/server/config", headers=auth, json={"auto_update": False}).get_json()
    assert config["auto_update"] is False and config["auto_update_locked"] is False


def test_start_after_update_and_after_rollback(tmp_path, github):
    layout = Layout(tmp_path / "updates")
    layout.write_json(layout.state_file, {"status": "applying", "staged_version": __version__,
                                          "previous_version": "1.0.0", "latest": {"version": __version__}})
    app = make_app(tmp_path, f'UPDATE_PATH="{(tmp_path / "updates").as_posix()}"')
    update = updater.get(app).as_json()
    assert update["status"] == "idle" and update["updated_from"] == "1.0.0" and update["latest"] is None

    layout.write_json(layout.last_start_file, {"rolled_back": True, "version": NEXT, "reason": "it stopped with code 1",
                                               "database_restored": True})
    app = make_app(tmp_path / "second", f'UPDATE_PATH="{(tmp_path / "updates").as_posix()}"')
    update = updater.get(app).as_json()
    assert update["status"] == "failed" and NEXT in update["error"] and "restored" in update["error"]
    assert not os.path.exists(layout.last_start_file)


def test_server_info_reports_restart(tmp_path, github):
    app = update_app(tmp_path, github)
    assert app.test_client().get("/api/v1/server/info").get_json()["restart_in"] is None


# --- Command line ---

def test_flags_become_env(tmp_path):
    args = cli.build_parser().parse_args([
        "--library", str(tmp_path / "a"), "--library", str(tmp_path / "b"), "--site-name", "123",
        "--no-allow-new-users", "--behind-proxy", "--no-auto-update", "--cors-origins", "https://a, https://b",
        "--data-dir", str(tmp_path / "data"),
    ])
    env = cli.flags_to_env(args)
    assert args.command == "serve"
    assert json.loads(env["FLASK_LIBRARY_PATHS"]) == [str(tmp_path / "a"), str(tmp_path / "b")]
    assert json.loads(env["FLASK_SITE_NAME"]) == "123"  # Stays text, not a number
    assert json.loads(env["FLASK_ALLOW_NEW_USERS"]) is False
    assert json.loads(env["FLASK_BEHIND_PROXY"]) is True
    assert json.loads(env["FLASK_AUTO_UPDATE"]) is False
    assert json.loads(env["FLASK_CORS_ORIGINS"]) == ["https://a", "https://b"]
    assert json.loads(env["FLASK_DATABASE_PATH"]) == str(tmp_path / "data" / "database.db")
    assert "FLASK_AUTO_APPROVE_NEW_USERS" not in env


def test_version_command(capsys):
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_flags_reach_the_app(tmp_path, monkeypatch):
    args = cli.build_parser().parse_args(["--site-name", "Home library", "--no-auto-update"])
    for key, value in cli.flags_to_env(args).items():
        monkeypatch.setenv(key, value)
    app = make_app(tmp_path)
    info = app.test_client().get("/api/v1/server/info").get_json()
    assert info["site_name"] == "Home library"
    assert app.config["AUTO_UPDATE"] is False


# --- Supervisor ---

def free_port():
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_maintenance_page(tmp_path):
    port = free_port()
    server = MaintenanceServer("127.0.0.1", port, "updating")
    assert server.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as api:
            urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{port}/manga/api/v1/manga?x=1", headers={"Origin": "http://localhost"}))
        assert api.value.code == 503
        assert json.load(api.value)["error"]["code"] == "server_updating"
        assert api.value.headers["Access-Control-Allow-Origin"] == "http://localhost"

        with pytest.raises(urllib.error.HTTPError) as page:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/manga/12")
        assert page.value.headers[MAINTENANCE_HEADER] == "updating"
        assert "location.reload" in page.value.read().decode()
    finally:
        server.stop()


class StubSupervisor(Supervisor):
    """Runs a small script instead of the real server."""

    def __init__(self, script, *args):
        super().__init__(*args)
        self.script = script

    def child_command(self):
        return [sys.executable, "-c", self.script]


READY_THEN_EXIT = "import os; open(os.environ['MYMANGALIB_READY_FILE'], 'w').close(); raise SystemExit(4)"


def test_supervisor_passes_exit_codes_through(tmp_path):
    supervisor = StubSupervisor(READY_THEN_EXIT, "127.0.0.1", free_port(), 1, str(tmp_path / "updates"))
    assert supervisor.run() == 4


def test_supervisor_runs_the_applied_update(tmp_path):
    layout = Layout(tmp_path / "updates")
    Path(layout.version_dir(NEXT), "mymangalib").mkdir(parents=True)
    Path(layout.version_dir(NEXT), "mymangalib", "__init__.py").write_text("")
    Path(layout.version_dir(NEXT), "frontend").mkdir()
    Path(layout.version_dir(NEXT), "frontend", "index.html").write_text("")
    layout.write_current(NEXT)
    layout.write_json(layout.apply_file, {"version": NEXT})
    script = ("import os, sys; open(os.environ['MYMANGALIB_READY_FILE'], 'w').close(); "
              "sys.exit(0 if os.environ['PYTHONPATH'].startswith(os.environ['EXPECTED']) "
              "and os.environ['MYMANGALIB_BUNDLE_FRONTEND'] else 9)")
    os.environ["EXPECTED"] = layout.version_dir(NEXT)
    try:
        supervisor = StubSupervisor(script, "127.0.0.1", free_port(), 1, layout.root)
        assert supervisor.run() == 0
    finally:
        del os.environ["EXPECTED"]
    assert not os.path.exists(layout.apply_file)  # It started, so it's no longer on trial
    assert layout.read_current() == NEXT


def test_supervisor_rolls_back_an_update_that_fails(tmp_path):
    layout = Layout(tmp_path / "updates")
    Path(layout.version_dir(NEXT), "mymangalib").mkdir(parents=True)
    Path(layout.version_dir(NEXT), "mymangalib", "__init__.py").write_text("")
    database, backup = tmp_path / "database.db", tmp_path / "backup.db"
    database.write_text("changed by the new version")
    backup.write_text("before the update")
    layout.write_current(NEXT)
    layout.write_json(layout.apply_file, {"version": NEXT, "previous": None, "previous_version": __version__,
                                          "backup": str(backup), "database": str(database)})

    # The new version crashes; after the rollback the old one starts and exits with 4
    script = ("import os, sys\n"
              "if os.environ.get('MYMANGALIB_BUNDLE_FRONTEND') is None and 'versions' in os.environ['PYTHONPATH']: sys.exit(1)\n"
              "open(os.environ['MYMANGALIB_READY_FILE'], 'w').close(); sys.exit(4)")
    supervisor = StubSupervisor(script, "127.0.0.1", free_port(), 1, layout.root)
    assert supervisor.run() == 4
    assert layout.read_current() is None
    assert database.read_text() == "before the update"
    note = layout.read_json(layout.last_start_file)
    assert note["rolled_back"] and note["version"] == NEXT and note["database_restored"]


def test_restart_exit_code_restarts(tmp_path):
    marker = tmp_path / "count"
    script = (f"import os, sys; p = {str(marker)!r}; n = int(open(p).read()) if os.path.exists(p) else 0; "
              "open(p, 'w').write(str(n + 1)); open(os.environ['MYMANGALIB_READY_FILE'], 'w').close(); "
              f"sys.exit({RESTART_EXIT_CODE} if n == 0 else 0)")
    supervisor = StubSupervisor(script, "127.0.0.1", free_port(), 1, str(tmp_path / "updates"))
    assert supervisor.run() == 0
    assert marker.read_text() == "2"
