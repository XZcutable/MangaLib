"""Serves the new front end (manga-site/dist) at / and moves the classic UI to /classic.

Turned on by setting FRONTEND_PATH to the built front end folder. Without it the classic UI stays at /.
"""
import os

from flask import Flask, send_from_directory

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
        response = send_from_directory(frontend_dir, "index.html", max_age=0)
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app

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
