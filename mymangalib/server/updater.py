"""Server updates from GitHub Releases.

Each release has a server bundle, `mymangalib-server-X.Y.Z.tar.gz` (made by scripts/release.mjs):
the mymangalib package, the built front end, requirements.txt and manifest.json. The updater:

1. checks the latest release every UPDATE_CHECK_HOURS (when automatic updates are on),
2. downloads the bundle in small chunks (resuming after a restart) and checks its sha256,
3. unpacks it next to the database, installing new Python packages if the bundle needs them,
4. and, only when the owner applies it, backs up the database and asks the supervisor
   (mymangalib/supervisor.py) to restart into the new version.

Applying needs the server to run under the supervisor (`mymangalib serve`, as the Docker image does).
"""
import hashlib, json, os, re, shutil, sqlite3, subprocess, sys, tarfile, threading, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from importlib import metadata

from flask import Flask, current_app

from ..update_files import Layout, PROTOCOL, RESTART_EXIT_CODE, remove
from ..version import __version__, is_newer

EXTENSION = "mymangalib_updater"
BUNDLE_PREFIX = "mymangalib-server-"
BUNDLE_SUFFIX = ".tar.gz"
CHUNK_SIZE = 1024 * 1024
CHUNK_PAUSE = 0.1           # Seconds between chunks, so a download never hogs a small connection
RESTART_DELAY = 3           # Seconds between "Apply" and the restart, so open pages can show the notice
KEEP_BACKUPS = 3
LOOP_INTERVAL = 5 * 60
STARTUP_DELAY = 60
SUPERVISED = "MYMANGALIB_SUPERVISED"

# idle: up to date (or never checked)  available: a newer version exists, not downloaded
# downloading  ready: downloaded, waiting for the owner  applying: restarting into it
# failed: the last download or update went wrong  needs_image: this update needs a new Docker image
STATUSES = ("idle", "checking", "available", "downloading", "ready", "applying", "failed", "needs_image")


class UpdateError(Exception):
    def __init__(self, message: str, status: str = "failed"):
        super().__init__(message)
        self.status = status


def init_app(app: Flask):
    root = app.config.get("UPDATE_PATH")
    if not root:
        database = app.config.get("DATABASE_PATH") or os.path.join(app.instance_path, "database.db")
        root = os.path.join(os.path.dirname(os.path.abspath(database)), "updates")
    app.config["UPDATE_PATH"] = root
    app.extensions[EXTENSION] = Updater(app, Layout(root))


def get(app: Flask | None = None) -> "Updater":
    return (app or current_app).extensions[EXTENSION]


def start_background(app: Flask):
    """Automatic checks. Only the served process runs them (mymangalib/child.py), not tests or `flask` commands."""
    get(app).start_background()


def now() -> datetime:
    return datetime.now(timezone.utc)


class Updater:
    def __init__(self, app: Flask, layout: Layout):
        self.app = app
        self.layout = layout
        self.lock = threading.RLock()
        self.worker: threading.Thread | None = None
        self.cancel = threading.Event()
        self.restart_at: float | None = None
        self.state = self.load_state()
        self.after_start()

    # --- State ---

    def load_state(self) -> dict:
        state = self.layout.read_json(self.layout.state_file) or {}
        if state.get("status") not in STATUSES:
            state["status"] = "idle"
        # Work that was running when the server stopped isn't running any more
        if state["status"] in ("checking", "downloading", "applying"):
            state["status"] = "available" if state.get("latest") else "idle"
        state.pop("progress", None)
        return state

    def save(self):
        with self.lock:
            saved = {key: value for key, value in self.state.items() if key != "progress"}
            try:
                self.layout.write_json(self.layout.state_file, saved)
            except OSError as error:
                print(f"WARNING: Couldn't save the update status: {error}")

    def set(self, **changes):
        with self.lock:
            self.state.update(changes)
            self.save()

    def after_start(self):
        """Notes what happened since the last start: an update applied, or one rolled back."""
        state = self.state
        rolled_back = self.layout.read_json(self.layout.last_start_file)
        if rolled_back and rolled_back.get("rolled_back"):
            restored = " Your database was restored from the backup made before the update." \
                if rolled_back.get("database_restored") else ""
            state["status"] = "failed"
            state["error"] = (f"Version {rolled_back.get('version')} didn't start ({rolled_back.get('reason')}), "
                              f"so the server went back to {__version__}.{restored}")
            remove(self.layout.last_start_file)

        staged = state.get("staged_version")
        if staged and not is_newer(staged, __version__):
            # Applied (or the image was replaced with one at least as new)
            if staged == __version__ and state.get("previous_version"):
                state["updated_from"] = state["previous_version"]
                state["updated_at"] = now().isoformat(timespec="seconds")
            state["staged_version"] = None
            if state["status"] in ("ready", "available", "needs_image"):
                state["status"] = "idle"
                state["error"] = None
        elif staged and state["status"] == "ready" and not self.layout.has_version(staged):
            state["staged_version"] = None
            state["status"] = "available"

        latest = state.get("latest")
        if latest and not is_newer(latest.get("version"), __version__):
            state["latest"] = None
            if state["status"] in ("available", "needs_image"):
                state["status"] = "idle"
        state["current_version"] = __version__
        self.save()

    def as_json(self) -> dict:
        with self.lock:
            state = dict(self.state)
        latest = state.get("latest")
        data = {
            "status": state["status"],
            "current_version": __version__,
            "latest": None if not latest else {
                "version": latest.get("version"),
                "notes": latest.get("notes") or "",
                "url": latest.get("url"),
                "published_at": latest.get("published_at"),
                "size": (latest.get("asset") or {}).get("size"),
                "has_bundle": bool(latest.get("asset")),
            },
            "staged_version": state.get("staged_version"),
            "progress": state.get("progress"),
            "error": state.get("error"),
            "last_check": state.get("last_check"),
            "updated_from": state.get("updated_from"),
            "updated_at": state.get("updated_at"),
            "auto_update": self.auto_update_enabled(),
            "auto_update_locked": self.auto_update_locked(),
            "can_apply": self.supervised(),
            "restart_in": self.restart_in(),
        }
        if not data["can_apply"]:
            data["apply_problem"] = ("This server wasn't started with `mymangalib serve` (as the Docker image is), "
                                     "so it can't restart itself. Download the new version instead.")
        return data

    # The same rules as server_settings.auto_update_*, without needing a request
    def auto_update_locked(self) -> bool:
        return not self.app.config.get("AUTO_UPDATE", True)

    def auto_update_enabled(self) -> bool:
        return not self.auto_update_locked() and bool(self.app.config.get("UPDATE_CHECKS", True))

    def supervised(self) -> bool:
        return os.environ.get(SUPERVISED) == "1" or bool(self.app.config.get("UPDATE_ASSUME_SUPERVISED"))

    def restart_in(self) -> float | None:
        if self.restart_at is None:
            return None
        return max(0.0, round(self.restart_at - time.time(), 1))

    # --- Checking ---

    def release_url(self) -> str:
        url = self.app.config.get("UPDATE_URL")
        if url:
            return url
        repo = self.app.config.get("UPDATE_REPO") or "XZcutable/MangaLib"
        return f"https://api.github.com/repos/{repo}/releases/latest"

    def check(self, automatic: bool = False) -> dict:
        with self.lock:
            if self.state["status"] in ("checking", "downloading", "applying"):
                return self.as_json()
            previous_status = self.state["status"]
            self.state["status"] = "checking"
        try:
            release = fetch_json(self.release_url())
        except UpdateError as error:
            self.set(status=previous_status if previous_status != "checking" else "idle",
                     error=f"Couldn't check for updates: {error}", last_check=now().isoformat(timespec="seconds"))
            return self.as_json()

        changes = {"last_check": now().isoformat(timespec="seconds"), "error": None}
        latest = release_info(release) if release else None
        if not latest or not is_newer(latest["version"], __version__):
            changes.update(status="idle", latest=None)
            if self.state.get("staged_version"):
                changes["status"] = "ready" if self.layout.has_version(self.state["staged_version"]) else "idle"
        else:
            changes["latest"] = latest
            staged = self.state.get("staged_version")
            if staged == latest["version"] and self.layout.has_version(staged):
                changes["status"] = "ready"
            elif not latest["asset"]:
                changes.update(status="available", error="This release doesn't have a server download yet.")
            elif previous_status == "needs_image" and (self.state.get("latest") or {}).get("version") == latest["version"]:
                changes["status"] = "needs_image"  # Still needs a new image; keep saying so
                changes.pop("error")
            else:
                changes["status"] = "available"
        self.set(**changes)

        if automatic and self.state["status"] == "available" and self.state["latest"].get("asset"):
            self.download()
        return self.as_json()

    def check_is_due(self) -> bool:
        last = self.state.get("last_check")
        if not last:
            return True
        hours = float(self.app.config.get("UPDATE_CHECK_HOURS") or 6)
        try:
            return now() - datetime.fromisoformat(last) > timedelta(hours=hours)
        except ValueError:
            return True

    # --- Downloading ---

    def download(self, wait: bool = False) -> dict:
        with self.lock:
            latest = self.state.get("latest")
            if self.state["status"] not in ("available", "failed") or not latest or not latest.get("asset"):
                return self.as_json()
            if self.worker and self.worker.is_alive():
                return self.as_json()
            self.cancel.clear()
            self.state["status"] = "downloading"
            self.state["error"] = None
            self.state["progress"] = {"done": 0, "total": latest["asset"].get("size") or 0}
            self.save()
            self.worker = threading.Thread(target=self.download_and_stage, args=(latest,),
                                           name="mymangalib-update", daemon=True)
            self.worker.start()
            worker = self.worker
        if wait or self.app.config.get("JOBS_INLINE"):
            worker.join()
        return self.as_json()

    def download_and_stage(self, latest: dict):
        version, asset = latest["version"], latest["asset"]
        try:
            bundle = self.fetch_bundle(asset)
            if self.cancel.is_set():
                return
            with self.lock:
                self.state["progress"] = {**(self.state.get("progress") or {}), "phase": "unpacking"}
            self.stage(bundle, version)
            remove(bundle)
            with self.lock:
                self.state["progress"] = None
            self.set(status="ready", staged_version=version, error=None)
            self.remove_old_versions()
            print(f"myMangaLib {version} is downloaded. Apply it in Settings > Server updates.")
        except UpdateError as error:
            with self.lock:
                self.state["progress"] = None
            self.set(status=error.status, error=str(error))
            print(f"WARNING: Update {version}: {error}")
        except Exception as error:  # A bug or a full disk shouldn't kill the thread silently
            with self.lock:
                self.state["progress"] = None
            self.set(status="failed", error=f"The download failed: {error}")
            print(f"WARNING: Update {version} failed: {error!r}")

    def fetch_bundle(self, asset: dict) -> str:
        """Downloads in CHUNK_SIZE ranges into <name>.part, continuing a partial download."""
        os.makedirs(self.layout.downloads, exist_ok=True)
        name = os.path.basename(asset["name"])
        final = os.path.join(self.layout.downloads, name)
        part = final + ".part"
        expected = asset.get("sha256")
        if not expected:
            raise UpdateError("The release doesn't list a checksum for the download, so it can't be checked.")
        if os.path.isfile(final) and file_sha256(final) == expected:
            return final

        total = int(asset.get("size") or 0)
        chunk = int(self.app.config.get("UPDATE_CHUNK_SIZE") or CHUNK_SIZE)
        pause = float(self.app.config.get("UPDATE_CHUNK_PAUSE", CHUNK_PAUSE))
        done = os.path.getsize(part) if os.path.isfile(part) else 0
        if total and done > total:
            remove(part)
            done = 0

        while not total or done < total:
            if self.cancel.is_set():
                return part
            end = done + chunk - 1 if not total else min(done + chunk, total) - 1
            response = open_url(asset["url"], {"Range": f"bytes={done}-{end}", "Accept": "application/octet-stream"})
            with response:
                if response.status == 206:
                    data = response.read()
                    if not data:
                        break
                    with open(part, "ab") as file:
                        file.write(data)
                    done += len(data)
                    if not total:
                        content_range = response.headers.get("Content-Range", "")
                        match = re.search(r"/(\d+)$", content_range)
                        total = int(match.group(1)) if match else 0
                else:
                    # The server ignored the range: take the whole file in one go
                    with open(part, "wb") as file:
                        shutil.copyfileobj(response, file)
                    done = total = os.path.getsize(part)
            with self.lock:
                self.state["progress"] = {"done": done, "total": total}
            if pause:
                time.sleep(pause)
            if not total:
                break

        if file_sha256(part) != expected:
            remove(part)
            raise UpdateError("The download was damaged (its checksum doesn't match). It starts over next time.")
        os.replace(part, final)
        return final

    def stage(self, bundle: str, version: str):
        """Unpacks the bundle into versions/<version>, ready to apply."""
        os.makedirs(self.layout.versions, exist_ok=True)
        target = self.layout.version_dir(version)
        temporary = target + ".partial"
        remove(temporary)
        try:
            with tarfile.open(bundle, "r:gz") as archive:
                safe_extract(archive, temporary)
        except (tarfile.TarError, OSError) as error:
            remove(temporary)
            raise UpdateError(f"The download couldn't be unpacked: {error}")

        manifest = Layout(temporary).read_json(os.path.join(temporary, "manifest.json")) or {}
        if manifest.get("version") != version or not os.path.isfile(os.path.join(temporary, "mymangalib", "__init__.py")):
            remove(temporary)
            raise UpdateError("The download isn't a myMangaLib server bundle for this version.")
        if int(manifest.get("protocol", 1)) > PROTOCOL:
            remove(temporary)
            raise UpdateError(f"Version {version} needs a newer Docker image. Run `docker compose pull` "
                              "and `docker compose up -d` to update.", status="needs_image")

        requirements = os.path.join(temporary, "requirements.txt")
        if os.path.isfile(requirements) and missing_requirements(requirements):
            self.install_requirements(requirements, os.path.join(temporary, "deps"), temporary)

        remove(target)
        os.replace(temporary, target)

    def install_requirements(self, requirements: str, deps: str, temporary: str):
        print("The update needs new Python packages; installing them next to it")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
                 "--quiet", "--target", deps, "-r", requirements],
                check=True, timeout=30 * 60, capture_output=True, text=True,
            )
        except (subprocess.SubprocessError, OSError) as error:
            remove(temporary)
            detail = getattr(error, "stderr", "") or str(error)
            print(f"WARNING: Installing the update's packages failed: {detail}")
            raise UpdateError("This update needs Python packages that couldn't be installed. Run "
                              "`docker compose pull` and `docker compose up -d` to update.", status="needs_image")

    def remove_old_versions(self):
        keep = {self.layout.read_current(), self.state.get("staged_version"), __version__}
        if not os.path.isdir(self.layout.versions):
            return
        for name in os.listdir(self.layout.versions):
            if name not in keep:
                remove(os.path.join(self.layout.versions, name))

    def discard(self) -> dict:
        self.cancel.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=30)
        with self.lock:
            if self.state["status"] == "applying":
                return self.as_json()
            staged = self.state.get("staged_version")
            if staged and staged != self.layout.read_current():
                remove(self.layout.version_dir(staged))
            remove(self.layout.downloads)
            latest = self.state.get("latest")
            self.state["progress"] = None
            self.set(staged_version=None, error=None,
                     status="available" if latest and is_newer(latest.get("version"), __version__) else "idle")
        return self.as_json()

    # --- Applying ---

    def apply(self) -> dict:
        """Backs up the database, switches to the downloaded version and restarts in RESTART_DELAY seconds."""
        with self.lock:
            staged = self.state.get("staged_version")
            if self.state["status"] != "ready" or not self.layout.has_version(staged):
                raise UpdateError("There's no downloaded update to apply.")
            if not self.supervised():
                raise UpdateError(self.as_json()["apply_problem"])
            database = self.app.config.get("DATABASE_PATH")
            backup = self.backup_database(database) if database else None
            self.layout.write_json(self.layout.apply_file, {
                "version": staged,
                "previous": self.layout.read_current(),
                "previous_version": __version__,
                "backup": backup,
                "database": os.path.abspath(database) if database else None,
                "applied_at": now().isoformat(timespec="seconds"),
            })
            self.layout.write_current(staged)
            delay = float(self.app.config.get("UPDATE_RESTART_DELAY", RESTART_DELAY))
            self.restart_at = time.time() + delay
            self.set(status="applying", previous_version=__version__, error=None)
        print(f"Applying update {staged}; restarting in {delay:g} seconds")
        threading.Timer(delay, self.restart).start()
        return self.as_json()

    def backup_database(self, database: str) -> str | None:
        if not os.path.isfile(database):
            return None
        os.makedirs(self.layout.backups, exist_ok=True)
        stamp = now().strftime("%Y%m%d-%H%M%S")
        target = os.path.join(self.layout.backups, f"database-{__version__}-{stamp}.db")
        # SQLite's backup copies a consistent snapshot even while the server is writing
        source, copy = sqlite3.connect(database), sqlite3.connect(target)
        try:
            source.backup(copy)
        finally:
            copy.close()
            source.close()
        backups = sorted(
            (os.path.join(self.layout.backups, name) for name in os.listdir(self.layout.backups) if name.endswith(".db")),
            key=os.path.getmtime,
        )
        for old in backups[:-KEEP_BACKUPS]:
            remove(old)
        return target

    def restart(self):
        hook = self.app.config.get("UPDATE_RESTART")
        if callable(hook):  # Tests
            hook()
            return
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(RESTART_EXIT_CODE)

    # --- Automatic checks ---

    def start_background(self):
        threading.Thread(target=self.loop, name="mymangalib-update-checks", daemon=True).start()

    def loop(self):
        time.sleep(STARTUP_DELAY)  # Let the startup scan and first visitors go first
        while True:
            try:
                if self.auto_update_enabled():
                    if self.check_is_due():
                        self.check(automatic=True)
                    elif self.state["status"] == "available":
                        self.download()  # Resumes a download a restart interrupted
            except Exception as error:
                print(f"WARNING: The automatic update check failed: {error!r}")
            time.sleep(LOOP_INTERVAL)


# --- Helpers ---

def open_url(url: str, headers: dict | None = None, timeout: float = 60):
    request = urllib.request.Request(url, headers={"User-Agent": f"myMangaLib/{__version__}", **(headers or {})})
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        raise UpdateError(f"{url} answered {error.code}")
    except (urllib.error.URLError, OSError) as error:
        raise UpdateError(f"can't reach {urllib.request.urlparse(url).netloc} ({getattr(error, 'reason', error)})")


def fetch_json(url: str) -> dict | None:
    """The release, or None when the repository has no releases yet (GitHub answers 404)."""
    request = urllib.request.Request(url, headers={
        "User-Agent": f"myMangaLib/{__version__}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise UpdateError(f"GitHub answered {error.code}")
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise UpdateError(str(getattr(error, "reason", error)))


def release_info(release: dict) -> dict | None:
    version = str(release.get("tag_name") or "").lstrip("vV")
    if not version or release.get("draft") or release.get("prerelease"):
        return None
    asset = None
    for candidate in release.get("assets") or []:
        name = candidate.get("name") or ""
        if name.startswith(BUNDLE_PREFIX) and name.endswith(BUNDLE_SUFFIX):
            digest = candidate.get("digest") or ""
            asset = {
                "name": name,
                "url": candidate.get("browser_download_url"),
                "size": candidate.get("size"),
                "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else None,
            }
            break
    return {
        "version": version,
        "notes": release.get("body") or "",
        "url": release.get("html_url"),
        "published_at": release.get("published_at"),
        "asset": asset,
    }


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: tarfile.TarFile, target: str):
    """Extracts only plain files and folders inside target (no links, devices or ../ paths)."""
    root = os.path.abspath(target)
    for member in archive.getmembers():
        path = os.path.abspath(os.path.join(root, member.name))
        if not (member.isfile() or member.isdir()) or os.path.commonpath([root, path]) != root:
            raise tarfile.TarError(f"unexpected entry {member.name!r}")
    try:
        archive.extractall(root, filter="data")
    except TypeError:  # Python without extraction filters
        archive.extractall(root)


def missing_requirements(requirements: str) -> list[str]:
    """Requirements the running Python doesn't have (or has in a version outside the range)."""
    try:
        from packaging.requirements import Requirement
    except ImportError:
        Requirement = None
    missing = []
    with open(requirements, encoding="utf-8") as file:
        for line in file:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name = re.split(r"[<>=!~;\[\s]", line, maxsplit=1)[0]
            try:
                installed = metadata.version(name)
            except metadata.PackageNotFoundError:
                missing.append(line)
                continue
            if Requirement is not None:
                try:
                    requirement = Requirement(line)
                    if requirement.specifier and not requirement.specifier.contains(installed, prereleases=True):
                        missing.append(line)
                except Exception:
                    pass
    return missing
