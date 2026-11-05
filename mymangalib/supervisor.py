"""Runs the server as a child process so it can be restarted to apply an update.

While the server is starting (or restarting into an update), the supervisor holds the port itself and
answers every request with a short "updating" page, or a 503 `server_updating` error for /api/v1. When the
new server is ready it says so (a ready file), the supervisor lets go of the port, and the server takes it.

If an update doesn't start, the supervisor switches back to the previous version and restores the database
backup made just before the update.
"""
import json, os, shutil, signal, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .update_files import Layout, RESTART_EXIT_CODE, remove
from .version import __version__, is_newer

# How long a newly applied update gets to start before it's rolled back. Starting includes the
# database changes and the startup scan, so this is generous.
UPDATE_START_TIMEOUT = 15 * 60
PORT_WAIT = 15

# Where this (the image's) copy of the package is installed, so the child finds it without relying
# on the working directory
PACKAGE_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAINTENANCE_HEADER = "X-MyMangaLib-Maintenance"
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
         font: 16px/1.5 system-ui, sans-serif; background: #f9fafb; color: #111827; text-align: center; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #030712; color: #f3f4f6; }} p {{ color: #9ca3af; }} }}
  main {{ padding: 24px 16px; max-width: 28rem; }}
  p {{ color: #4b5563; }}
  .spinner {{ width: 40px; height: 40px; margin: 0 auto 20px; border: 4px solid #9ca3af55;
             border-top-color: #2563eb; border-radius: 50%; animation: spin 1s linear infinite; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style></head>
<body><main>
  <div class="spinner" aria-hidden="true"></div>
  <h1>{title}</h1>
  <p>{message}</p>
  <p>This page comes back by itself when the server is ready.</p>
</main>
<script>
  // Asks for this same page until the real server answers it, then shows it
  async function poll() {{
    try {{
      const response = await fetch(location.href, {{ cache: "no-store" }})
      if (!response.headers.get("{header}")) return location.reload()
    }} catch (error) {{}}
    setTimeout(poll, 2000)
  }}
  setTimeout(poll, 2000)
</script>
</body></html>
"""
MESSAGES = {
    "starting": ("myMangaLib is starting", "The server is loading the library."),
    "updating": ("myMangaLib is updating", "A new version is being installed. This usually takes under a minute."),
}


def installed_in_site_packages() -> bool:
    import site
    folders = [*site.getsitepackages(), site.getusersitepackages()]
    return any(os.path.normcase(os.path.abspath(folder)) == os.path.normcase(PACKAGE_PARENT) for folder in folders)


def log(message: str):
    print(f"[supervisor] {message}", flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MaintenanceServer:
    """Answers requests while the real server is down."""

    def __init__(self, host: str, port: int, mode: str):
        self.host, self.port, self.mode = host, port, mode
        self.httpd = None

    def start(self) -> bool:
        handler = type("Handler", (MaintenanceHandler,), {"mode": self.mode})
        deadline = time.time() + PORT_WAIT
        while True:
            try:
                self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
                break
            except OSError as error:
                # The old server can take a moment to let go of the port
                if time.time() > deadline:
                    log(f"Can't listen on {self.host}:{self.port}: {error}")
                    return False
                time.sleep(0.2)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        return True

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


class MaintenanceHandler(BaseHTTPRequestHandler):
    mode = "starting"
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def cors(self):
        # The Android app calls from another origin; without these it can't read the 503
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header(MAINTENANCE_HEADER, self.mode)
        self.end_headers()

    def answer(self):
        if "/api/v1/" in self.path:
            body = json.dumps({"error": {
                "code": "server_updating" if self.mode == "updating" else "server_starting",
                "message": MESSAGES[self.mode][0],
            }}).encode()
            content_type = "application/json"
        else:
            title, message = MESSAGES[self.mode]
            body = PAGE.format(title=title, message=message, header=MAINTENANCE_HEADER).encode()
            content_type = "text/html; charset=utf-8"
        self.send_response(503)
        self.cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Retry-After", "5")
        self.send_header(MAINTENANCE_HEADER, self.mode)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = answer


class Supervisor:
    def __init__(self, host: str, port: int, threads: int, update_path: str):
        self.host, self.port, self.threads = host, port, threads
        self.layout = Layout(update_path)
        self.child: subprocess.Popen | None = None
        self.stopping = False

    # --- Which code to run ---

    def choose_version(self) -> str | None:
        """The applied update, when it's newer than the code this server was installed with. A newer image
        (docker pull) wins over an older applied update."""
        applied = self.layout.read_current()
        if not applied:
            return None
        if is_newer(applied, __version__) and self.layout.has_version(applied):
            return applied
        if not is_newer(applied, __version__):
            log(f"The installed version {__version__} is newer than the applied update {applied}; using it")
            self.layout.write_current(None)
        else:
            log(f"The files for update {applied} are missing; using the installed version {__version__}")
        return None

    def child_env(self, version: str | None, ready_file: str) -> dict:
        env = os.environ.copy()
        env["MYMANGALIB_SUPERVISED"] = "1"
        env["MYMANGALIB_READY_FILE"] = ready_file
        env.pop("MYMANGALIB_BUNDLE_FRONTEND", None)
        # A source checkout (python -m mymangalib) needs its folder on the path; an installed package
        # is already found in site-packages, which must stay behind the standard library
        paths = [] if installed_in_site_packages() else [PACKAGE_PARENT]
        if version:
            folder = self.layout.version_dir(version)
            paths = [folder, os.path.join(folder, "deps"), *paths]
            if os.path.isfile(os.path.join(folder, "frontend", "index.html")):
                env["MYMANGALIB_BUNDLE_FRONTEND"] = os.path.join(folder, "frontend")
        if env.get("PYTHONPATH"):
            paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(paths)
        return env

    def child_command(self) -> list[str]:
        # -P: don't put the working directory first on the path, where a source checkout (like /mangalib
        # in the image) would hide the applied update
        return [sys.executable, "-P", "-m", "mymangalib.child",
                "--host", self.host, "--port", str(self.port), "--threads", str(self.threads)]

    # --- Running ---

    def run(self) -> int:
        self.handle_signals()
        mode = "starting"
        while not self.stopping:
            code = self.run_once(mode)
            if self.stopping:
                return 0
            if code == RESTART_EXIT_CODE:
                mode = "updating"
                continue
            return code if isinstance(code, int) else 1
        return 0

    def run_once(self, mode: str):
        version = self.choose_version()
        pending = self.layout.read_json(self.layout.apply_file)
        verifying = bool(pending) and pending.get("version") == version
        log(f"Starting myMangaLib {version or __version__}" + (" (just updated)" if verifying else ""))

        maintenance = MaintenanceServer(self.host, self.port, mode)
        if not maintenance.start():
            return 1
        ready_file = os.path.join(self.layout.root, f"ready-{os.getpid()}")
        remove(ready_file)
        os.makedirs(self.layout.root, exist_ok=True)
        try:
            self.child = subprocess.Popen(self.child_command(), env=self.child_env(version, ready_file))
            ready, code = self.wait_until_ready(ready_file, UPDATE_START_TIMEOUT if verifying else None)
        finally:
            maintenance.stop()
            remove(ready_file)

        if not ready:
            if verifying:
                reason = "it took too long to start" if code == "timeout" else f"it stopped with code {code}"
                self.roll_back(pending, reason)
                return RESTART_EXIT_CODE
            return code

        if verifying:
            remove(self.layout.apply_file)
            log(f"Updated to {version}")
        return self.child.wait()

    def wait_until_ready(self, ready_file: str, timeout: float | None):
        deadline = time.time() + timeout if timeout else None
        while True:
            if os.path.exists(ready_file):
                return True, None
            code = self.child.poll()
            if code is not None:
                return False, code
            if self.stopping:
                return False, 0
            if deadline and time.time() > deadline:
                self.child.terminate()
                self.child.wait()
                return False, "timeout"
            time.sleep(0.1)

    def roll_back(self, pending: dict, reason: str):
        version = pending.get("version")
        log(f"Update {version} didn't start ({reason}); going back to the previous version")
        self.layout.write_current(pending.get("previous"))
        restored = False
        backup, database = pending.get("backup"), pending.get("database")
        if backup and database and os.path.isfile(backup):
            try:
                for suffix in ("-wal", "-shm"):
                    remove(database + suffix)
                shutil.copy2(backup, database)
                restored = True
            except OSError as error:
                log(f"Couldn't restore the database backup {backup}: {error}")
        self.layout.write_json(self.layout.last_start_file, {
            "rolled_back": True,
            "version": version,
            "restored_version": pending.get("previous_version"),
            "reason": reason,
            "database_restored": restored,
            "at": now(),
        })
        remove(self.layout.apply_file)

    def handle_signals(self):
        def stop(signum, frame):
            self.stopping = True
            if self.child and self.child.poll() is None:
                self.child.terminate()
        for name in ("SIGTERM", "SIGINT"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), stop)
