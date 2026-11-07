# myMangaLib

Self-hosted manga server (Python/Flask, SQLite) with two front ends:
- **Classic UI:** Jinja templates in `mymangalib/templates`, cookie sessions, old `/api` routes. It must keep working.
- **New UI:** the React app in `manga-site/`. It runs in the browser and as the Android app (Capacitor), and talks to `/api/v1` with bearer tokens. See `manga-site/CLAUDE.md`.

Android releases are published to https://github.com/XZcutable/MangaLib/releases. iOS is deferred.

## Working rules
- Commit or push only when the user asks. Since the mobile-app PR was merged, the user has had work committed straight to `main`; otherwise create a branch first (e.g. `feature/...`). The user merges PRs themselves.
- `origin` is the user's GitLab (`https://gitlab.home/xzcutable/mymanga.git`). GitHub (`XZcutable/MangaLib`) only hosts the APK releases.
- Never commit secrets. `C:\Users\RNGAb\.mymangalib\` holds the release signing key (`release.jks`, `release.properties`) and the GitHub token (`github-token`); all stay outside the repo.
- `manga/` holds large real sample `.cbz` volumes (gitignored); use it for manual testing.

## Backend
- Run (Windows, repo root): `.venv/Scripts/python -m flask --app mymangalib run --port 5000 --host 127.0.0.1`. Use `--host 0.0.0.0` when a phone needs to reach it.
- Tests: `.venv/Scripts/python -m pytest` (all should pass). Fixtures in `tests/conftest.py`: `make_app`, `scan`, `add_volume`.
- Config: `config.toml` (defaults in `ENV.DEFAULT_CONFIG`, `mymangalib/constants.py`). Any key can be overridden with a `FLASK_<KEY>` env var (`from_prefixed_env`), e.g. `FLASK_CONFIG_PATH`, `FLASK_DATABASE_PATH`, `FLASK_FRONTEND_PATH`, `FLASK_CORS_ORIGINS`.
- `FRONTEND_PATH` set to a built `manga-site/dist` serves the new UI at `/` and moves the classic UI to `/classic` (`mymangalib/frontend.py`). It also serves `/manifest.webmanifest` from the build with the site name filled in (no login needed; exempted at the top of `auth.before_app_request`). `index.html` always goes through `index_page()`, even when requested by name, because the PWA service worker stores that copy.
- Sub-paths (`https://example.com/manga/`): the prefix arrives as `SCRIPT_NAME`, from `X-Forwarded-Prefix` (ProxyFix) or `URL_PREFIX` (`UrlPrefixMiddleware`). Rules that keep it working:
  - `frontend.py` writes `<base href="{script_root}/">` into `index.html`, and the app is built with relative asset paths (`base: "./"`).
  - The app reads the prefix from `document.baseURI` (`lib/base.js`) for the router `basename` and API calls.
  - API responses return paths without the prefix (`api_path()` in `api_v1.py`), because clients add their server address, which includes it.
  - Classic templates use `url_for('static', ...)`, never a hard-coded `/static/`.
  - `tests/test_frontend.py` covers both proxy styles.
- No migration tool: new columns must be nullable and are added at startup by `add_missing_columns()` in `mymangalib/database.py`; indexes declared on the models are added by `add_missing_indexes()`. Don't drop columns: older versions still write them, which would break a rollback. Backfills go there too (e.g. `fill_missing_release_years`).
- Settings the owner changes from the app live in the `ServerSetting` table (`server/server_settings.py`) and win over `config.toml`: on/off ones in `EDITABLE`, text ones (`SITE_NAME`) in `EDITABLE_TEXT`.
- Invites (`server/invites.py`, `/api/v1/invites`): shared as `<server>/join?code=...` (the new UI's `/join` page, or the classic `auth.join` redirect to `/register?invite=`). Only the code's hash is stored. What an invite allows is decided when it's used, from its creator's current role: an admin's works while registration is closed and approves the account; anyone else's needs `ALLOW_NEW_USERS` and follows auto-approve. `User.invited_by` records the inviter. `PUBLIC_URL` (owner text setting) is the address invite links should use; empty means the app shares the address it's connected to.
- Usernames: `username_problem()` holds the rule (no leading or trailing spaces) and `rename_user()` the change, both in `auth.py`. `User.must_change_username` is set by admins or at login when a stored name breaks the rule. While it's set, only the endpoints in `API_RENAME_ENDPOINTS` / `CLASSIC_RENAME_ENDPOINTS` work, so add any endpoint a flagged user must still reach there.
- Classic routes: `/all`, `/latest` etc. are link aliases with no view (requesting them raises `KeyError`). The real pages are under `/manga/` (e.g. `/manga/all`); use those in tests.
- Series details: `server/comicinfo.py` reads/writes `ComicInfo.xml` (file work only); `server/metadata.py` validates, imports on scan (once, tracked by `MangaMetadata.metadata_source`) and applies edits. Users suggest (`MetadataSuggestion`), admins approve; approved edits write only the changed fields, and summary/year go to the first volume only (they're per volume in ComicInfo).
- Slow file work (metadata write-back, crunch/unpack in `server/repack.py`) runs through `server/jobs.py`: one in-memory worker, polled with `GET /admin/jobs/<id>`. Tests set `JOBS_INLINE`. Temporary copies are hidden `.partial` files the scanner skips.
- Per-chapter read marks (`UserChapterData`) and saved positions are keyed by chapter number; crunch/unpack remaps them by chapter title after the rescan.
- Crunch (`repack.crunch_series`) is all or nothing per series and never leaves pages unreadable: it builds every archive, puts them in place, rescans with the old folders skipped (`scan_manga(skip=...)`), commits, and only then deletes the old images. Loose images in a series folder go to `<series>/<series>.cbz`. "Crunch all series" (`POST /library/crunch/preview`, then `POST /library/crunch`) runs as one job with `manga_id` None (`jobs.library_job()`); single-series file jobs answer 409 while it runs, and so does applying a server update while any job runs.
- Old images a crunch couldn't delete (file in use on Windows) are stored in `PendingDeletion` (`server/disposal.py`). The scanner skips their folders so they don't come back as chapters; the owner sees them in Settings → Library (`GET /library/leftovers`) and deletes them again with `POST /library/leftovers/delete`. A file whose `.cbz` is gone is kept and unlisted.
- Page image URLs carry `?v=` (a hash of the chapter path), because a crunch, unpack or move can give a chapter number to different files and pages are cached for days.
- CORS (`api_v1.init_app`) lists the allowed HTTP methods. A route with a new method won't work from the Android app until the method is added there.
- **Versions:** server and app share one version, in `pyproject.toml` and `manga-site/package.json` (`tests/test_updates.py` checks they match; `pnpm release` bumps both). The server reads it from `mymangalib/version.py`, the app from `__APP_VERSION__` (Vite `define`, `lib/version.js`). `API_VERSION` (api_v1.py) / `APP_API_VERSION` (`lib/features.js`) are separate and gate features.

### Launcher and server updates
- `mymangalib serve` (`cli.py`, also `python -m mymangalib`) turns flags into `FLASK_<KEY>` env vars, then runs `supervisor.py`, which starts the real server (`python -P -m mymangalib.child`) as a child. The Docker image's `ENTRYPOINT` is `mymangalib serve`, so `docker run <image> --flag` works. Keep `child.py`'s flags stable: an older supervisor starts newer versions through it.
- While the child starts or restarts, the supervisor holds the port and answers 503 (JSON `server_updating`/`server_starting` for `/api/v1`, an auto-reloading page otherwise, header `X-MyMangaLib-Maintenance`). The child writes `MYMANGALIB_READY_FILE` after `create_app()`, then takes the port.
- `server/updater.py` checks GitHub Releases (`UPDATE_REPO`, or `UPDATE_URL` for testing), downloads `mymangalib-server-X.Y.Z.tar.gz` in Range chunks (sha256 from the asset `digest`), and unpacks it to `<UPDATE_PATH>/versions/X.Y.Z` (Docker: `/data/updates`; layout in `update_files.py`). Apply = DB backup + `current` pointer + exit code 75; the supervisor restarts into it and rolls back (pointer + DB backup) if it doesn't become ready. A newer image wins over an older applied update.
- The bundle is made by `scripts/make_server_bundle.py`, called by `scripts/release.mjs` (`pnpm release` in `manga-site` runs it). Dependencies are listed only in `pyproject.toml`; the bundle gets a `requirements.txt` made from them, because installed servers' updaters read it. Bump `update_files.PROTOCOL` when the bundle layout or the supervisor/child handshake changes; a bundle with a higher protocol reports `needs_image`.
- `AUTO_UPDATE=false` (`--no-auto-update`) is a hard off and locks the owner's `UPDATE_CHECKS` switch (in `EDITABLE`); manual checks still work. Applying needs `MYMANGALIB_SUPERVISED=1` (tests set `UPDATE_ASSUME_SUPERVISED` and `UPDATE_RESTART`).
- Apply from inside the app is only possible under the supervisor; `flask run` and plain `waitress-serve` can check and download but not apply.

### `/api/v1` conventions
- Routes: `blueprints/api_v1.py` (users) and `blueprints/api_v1_admin.py` (owner/admin). Shared query logic lives in `mymangalib/server/` so the old `/api` and v1 don't duplicate it.
- Auth: protect routes with `@api_access(Access.X)`; return errors with `api_error(status, code, message)` (JSON `{"error": {code, message}}`), both in `mymangalib/auth.py`. Never redirect from `/api/v1`.
- Tokens are stored hashed (SHA-256) in `ApiToken`. Image routes also accept `?t=<token>` because `<img>` can't send headers. Responses include ready-made `cover_url` / `image_url`.
- `GET /auth/me` returns `pending_users` for admins; the app polls it to keep the approval queue live.
- `server/info` has `name` (always "myMangaLib"; the app checks it to recognize a server, so never change it) and `site_name` (the display name: `SITE_NAME` config, changeable by the owner via `PUT /server/config`).

### Naming
- **Recently Updated** = most recent new content (`Manga.last_updated`).
- **New Releases** = series that came out most recently (`Manga.release_year`).

## Docker
`Dockerfile` has a Node stage that builds `manga-site` and sets `FRONTEND_PATH`; the server runs with waitress under `mymangalib serve`. Releases push it to `ghcr.io/xzcutable/mangalib` (tags `X.Y.Z`, `X.Y`, `X`, `latest`), which `compose.yml` uses; `compose.build.yml` builds locally instead. Pushing needs a classic token with `write:packages` in `~/.mymangalib/ghcr-token` (GHCR doesn't take fine-grained tokens).
- `FLASK_LIBRARY_PATHS='["/var/manga"]'`: `LIBRARY_PATHS` folders are registered and scanned at startup, but only when no library folders exist yet (`add_configured_paths` in `server/scanner.py`). `Manga.path` and `Chapter.path` are absolute (pages store only file names), so upgraded servers keep their old folders, and adding a second mount of the same files would duplicate every manga. To move a library, rewrite the paths instead: `library_paths.move_library()` (`PUT /library/paths`, `LIBRARY_MOVES` / `--library-moved` at startup). `server/move.py` moves one series' files to another library folder as a job. Both go through `library_paths.rewrite_prefix()`, which matches either slash after the folder (the scanner joins with `os.path.join`). The scan runs before requests are served, because a background scan could collide with SQLite's write lock.
- Upgrading from the original version (before `41d5c34`): see `UPGRADING.md`. Old Docker installs keep the DB inside the container at `/usr/local/var/mymangalib-instance/database.db`.
  - To rehearse an upgrade, check out `41d5c34` in a `git worktree`. Its image only builds with `apt upgrade -y` in the Dockerfile and `SQLAlchemy<2.1` in `requirements.txt`; the old code crashes on SQLAlchemy 2.1.
- Data: one `/data` volume (`FLASK_DATA_DIR`). `cli.docker_data_paths()` keeps older containers on `/var/db` + `/var/config` (or `./data/db` + `./data/config` under the new mount) when a database is there, or when `/var/db` is mounted on a fresh start. The image declares only `/data` as a `VOLUME`, so a mount at `/var/db` is always the user's own.
- `PYTHONUNBUFFERED=1` is needed, or nothing the server prints reaches `docker compose logs`.
- **Testing on this PC:** Docker isn't on Windows; it runs inside WSL Ubuntu (`wsl -d Ubuntu --cd /mnt/c/Users/RNGAb/Documents/projects/mymanga -- bash -lc "docker compose -f compose.yml -f compose.build.yml up -d --build"`). Run `wsl` from PowerShell: Git Bash rewrites the `/mnt/c/...` path. The user's account is in the docker group, so no sudo is needed.
  - WSL stops the distro when no `wsl` command is running, which kills the container mid-test (it looks like a crash with exit code 0). Keep a background `wsl -d Ubuntu -- sleep infinity` running while testing.
  - localhost:5000 on Windows reaches the container, but the LAN doesn't. For the phone, use `adb reverse tcp:5000 tcp:5000` and connect the app to `localhost:5000`.
  - Compose data goes to `./data` (gitignored); delete it to test a fresh first start. To test the old layout, put a database in `./data/db/database.db`.

## Browser checks
No Chrome on this PC: drive Edge (`C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`) with `playwright-core`, via `chromium.launch({ executablePath })`. The scratchpad doesn't persist between sessions, so install `playwright-core` into a new scratch folder. Use a recent version: 1.47 fails to launch because Edge dropped the old headless mode. Use a phone-sized viewport (412×915) and read the screenshots.
