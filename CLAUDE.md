# myMangaLib

Self-hosted manga server (Python/Flask, SQLite) with two front ends:
- **Classic UI:** Jinja templates in `mymangalib/templates`, cookie sessions, old `/api` routes. It must keep working.
- **New UI:** the React app in `manga-site/`. It runs in the browser and as the Android app (Capacitor), and talks to `/api/v1` with bearer tokens. See `manga-site/CLAUDE.md`.

Android releases are published to https://github.com/XZcutable/MangaLib/releases. iOS is deferred.

## Working rules
- Commit or push only when the user asks. If on `main`, create a branch first (e.g. `feature/...`). The user merges PRs themselves.
- Never commit secrets. `C:\Users\RNGAb\.mymangalib\` holds the release signing key (`release.jks`, `release.properties`) and the GitHub token (`github-token`); all stay outside the repo.
- `manga/` holds large real sample `.cbz` volumes (gitignored); use it for manual testing.

## Backend
- Run (Windows, repo root): `.venv/Scripts/python -m flask --app mymangalib run --port 5000 --host 127.0.0.1`. Use `--host 0.0.0.0` when a phone needs to reach it.
- Tests: `.venv/Scripts/python -m pytest` (all should pass). Fixtures in `tests/conftest.py`: `make_app`, `scan`, `add_volume`.
- Config: `config.toml` (defaults in `ENV.DEFAULT_CONFIG`, `mymangalib/constants.py`). Any key can be overridden with a `FLASK_<KEY>` env var (`from_prefixed_env`), e.g. `FLASK_CONFIG_PATH`, `FLASK_DATABASE_PATH`, `FLASK_FRONTEND_PATH`, `FLASK_CORS_ORIGINS`.
- `FRONTEND_PATH` set to a built `manga-site/dist` serves the new UI at `/` and moves the classic UI to `/classic` (`mymangalib/frontend.py`).
- No migration tool: new columns must be nullable and are added at startup by `add_missing_columns()` in `mymangalib/database.py`. Backfills go there too (e.g. `fill_missing_release_years`).
- Switches the owner changes from the app (registration, auto-approve) live in the `ServerSetting` table (`server/server_settings.py`), not only in `config.toml`.

### `/api/v1` conventions
- Routes: `blueprints/api_v1.py` (users) and `blueprints/api_v1_admin.py` (owner/admin). Shared query logic lives in `mymangalib/server/` so the old `/api` and v1 don't duplicate it.
- Auth: protect routes with `@api_access(Access.X)`; return errors with `api_error(status, code, message)` (JSON `{"error": {code, message}}`), both in `mymangalib/auth.py`. Never redirect from `/api/v1`.
- Tokens are stored hashed (SHA-256) in `ApiToken`. Image routes also accept `?t=<token>` because `<img>` can't send headers. Responses include ready-made `cover_url` / `image_url`.
- `GET /auth/me` returns `pending_users` for admins; the app polls it to keep the approval queue live.

### Naming
- **Recently Updated** = most recent new content (`Manga.last_updated`).
- **New Releases** = series that came out most recently (`Manga.release_year`).

## Docker
`Dockerfile` has a Node stage that builds `manga-site` and sets `FRONTEND_PATH`; the server runs with waitress.
- `FLASK_LIBRARY_PATHS='["/var/manga"]'`: `LIBRARY_PATHS` folders are registered and scanned at startup, but only when no library folders exist yet (`add_configured_paths` in `server/api.py`). Pages are stored with absolute paths, so upgraded servers keep their old folders, and adding a second mount of the same files would duplicate every manga.
- Upgrading from the original version (before `41d5c34`): see `UPGRADING.md`. Old Docker installs keep the DB inside the container at `/usr/local/var/mymangalib-instance/database.db`. The scan runs before requests are served, because a background scan could collide with SQLite's write lock.
- `PYTHONUNBUFFERED=1` is needed, or nothing the server prints reaches `docker compose logs`.
- **Testing on this PC:** Docker isn't on Windows; it runs inside WSL Ubuntu (`wsl -d Ubuntu --cd /mnt/c/Users/RNGAb/Documents/projects/mymanga -- bash -lc "docker compose up -d --build"`). The user's account is in the docker group, so no sudo is needed.
  - WSL stops the distro when no `wsl` command is running, which kills the container mid-test (it looks like a crash with exit code 0). Keep a background `wsl -d Ubuntu -- sleep infinity` running while testing.
  - localhost:5000 on Windows reaches the container, but the LAN doesn't. For the phone, use `adb reverse tcp:5000 tcp:5000` and connect the app to `localhost:5000`.
  - Compose data goes to `./data` (gitignored); delete it to test a fresh first start.
