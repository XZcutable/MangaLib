"""Serves the new front end (manga-site/dist) at / and moves the classic UI to /classic.

Turned on by setting FRONTEND_PATH to the built front end folder. Without it the classic UI stays at /.

Also handles running under a sub-path behind a reverse proxy (e.g. https://example.com/manga/), from
URL_PREFIX or the proxy's X-Forwarded-Prefix header (with BEHIND_PROXY).
"""
import os, re

from flask import Flask, request, send_from_directory
from markupsafe import escape

CLASSIC_PREFIX = "/classic"
# Paths the server answers itself instead of the front end. The classic pages link to /static directly.
PASSTHROUGH_PREFIXES = ("/api/", "/static/")
ONE_YEAR = 365 * 24 * 60 * 60

class FrontendMiddleware:
    def __init__(self, server_wsgi, frontend_dir: str):
        self.server = server_wsgi
        self.frontend = create_frontend_app(frontend_dir).wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or "/"

        if path.startswith(PASSTHROUGH_PREFIXES):
            return self.server(environ, start_response)

        if path == CLASSIC_PREFIX or path.startswith(CLASSIC_PREFIX + "/"):
            # Mounting under a script name makes url_for() add /classic to every link the classic UI builds
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + CLASSIC_PREFIX
            environ["PATH_INFO"] = path[len(CLASSIC_PREFIX):] or "/"
            return self.server(environ, start_response)

        return self.frontend(environ, start_response)

def create_frontend_app(frontend_dir: str) -> Flask:
    frontend_dir = os.path.abspath(frontend_dir)
    app = Flask("mymangalib_frontend", static_folder=None)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path: str):
        file_path = os.path.join(frontend_dir, path)
        if path and os.path.isfile(file_path):
            # Vite puts a content hash in asset file names, so they can be cached for good
            max_age = ONE_YEAR if path.startswith("assets/") else 0
            return send_from_directory(frontend_dir, path, max_age=max_age)
        # Every other path is a page of the app, which its router handles
        return index_page(frontend_dir)

    return app

BASE_TAG = re.compile(r"<base\s[^>]*>", re.IGNORECASE)

def index_page(frontend_dir: str):
    """index.html with a <base> tag for the path the server is reached at. The app is built with relative
    asset paths and reads its base from this tag, so the same build works at / and under a sub-path."""
    with open(os.path.join(frontend_dir, "index.html"), encoding="utf-8") as file:
        html = file.read()
    base_tag = f'<base href="{escape(request.script_root)}/" />'
    html = BASE_TAG.sub(base_tag, html, count=1) if BASE_TAG.search(html) else html.replace("<head>", f"<head>{base_tag}", 1)
    return html, 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache"}

class UrlPrefixMiddleware:
    """For a proxy that passes /manga/... through unchanged: serves the app at that prefix. Requests outside
    it still work, so the server stays reachable directly on its own address too."""
    def __init__(self, server_wsgi, prefix: str):
        self.server = server_wsgi
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or "/"
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
        return self.server(environ, start_response)

def install_url_prefix(app: Flask):
    """URL_PREFIX = '/manga' serves everything under /manga when the proxy doesn't remove the prefix."""
    prefix = (app.config.get("URL_PREFIX") or "").strip().rstrip("/")
    if not prefix:
        return
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    print(f"Serving under {prefix}/")
    app.wsgi_app = UrlPrefixMiddleware(app.wsgi_app, prefix)

def install(app: Flask):
    """Wraps the app when FRONTEND_PATH points at a built front end."""
    frontend_dir = app.config.get("FRONTEND_PATH")
    if not frontend_dir:
        return
    if not os.path.isfile(os.path.join(frontend_dir, "index.html")):
        print(f"WARNING: FRONTEND_PATH '{frontend_dir}' has no index.html. Build it with 'pnpm build' in manga-site/.")
        print("WARNING: Serving the classic UI at / instead.")
        return
    print(f"Serving the new front end from {frontend_dir}; the classic UI is at {CLASSIC_PREFIX}/")
    app.wsgi_app = FrontendMiddleware(app.wsgi_app, frontend_dir)
    app.config["CLASSIC_UI_PATH"] = CLASSIC_PREFIX + "/"
