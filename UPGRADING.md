# Upgrading from the original version

This guide is for servers running myMangaLib from before the new interface and mobile app, up to commit `41d5c34` (March 2026). The upgrade keeps your accounts, library, reading progress, favorites, queue and tags.

## What changes

- **New interface.** The Docker image serves the new interface at `/`. The classic one moves to `/classic/` and still works.
- **Android app.** It connects to your server ([releases](https://github.com/XZcutable/MangaLib/releases)).
- **Database.** It's upgraded automatically on the first start. Two tables (`api_token`, `server_setting`) and two columns (`manga.release_year`, `manga.last_updated`) are added, and release years are filled in from file names. Nothing existing is changed or removed.
- **Sign-up settings.** "Allow new users" and "Auto-approve" can now be changed in Settings. Once changed there, the saved setting wins over `config.toml`.
- **History** now lists only manga you have opened. Before, it also listed manga you had only favorited, queued or marked as read.
- **Old links.** Bookmarks to a series page (`/manga/3`) open in the new interface. Bookmarks to a reader page (`/manga/3/2/5`) or a list (`/manga/favorites`) don't; use `/classic/...` instead.

> **Can't stay on the old version as-is:** its Dockerfile no longer builds (`apt upgrade` waits for an answer), and the old code fails to start with SQLAlchemy 2.1, which pip now installs by default. An image you already built keeps working, but rebuilding it doesn't.

## Before you start

1. **Find your library folder as the server sees it.** Classic interface → Settings → Config → Local Paths (for example `/var/manga`). Every page is stored with its full path, so the upgraded server must see your manga at the **same path**.
2. **Note your owner username and password.** Accounts carry over unchanged.
3. **Back up the database and config** (steps below). The upgrade can be rolled back only if you have them.

---

## Docker

The original `compose.yml` had no volumes, so the database and config live **inside the container**. Copy them out first.

> ⚠️ Don't run `docker compose down` or `docker compose up --build` with the new files until step 2 is done. Either one replaces the old container, and your data goes with it.

**Run every command below from the project folder**: the folder you cloned, which holds `compose.yml` and `Dockerfile`. For example:

```sh
cd ~/mymanga
ls compose.yml        # should print compose.yml
```

From any other folder, `docker compose` stops with `no configuration file provided: not found`. Paths like `./data` are also relative to this folder.

1. **Find the old container:**

   ```sh
   docker ps -a            # e.g. mymanga-mangalib-1
   ```

2. **Copy the database and config out of it**, from the project folder:

   ```sh
   mkdir -p data/db data/config
   docker cp <container>:/usr/local/var/mymangalib-instance/database.db data/db/database.db
   docker cp <container>:/var/config/config.toml data/config/config.toml
   ```

   If you added your own volumes for these, copy from those instead. Keep a second copy of both files somewhere safe; that's your backup.

3. **Stop the old container:** `docker stop <container>`. Don't remove it until the new version works.

4. **Get the new version:** `git pull`.

5. **Point `compose.yml` at your manga.** In `- ./manga:/var/manga:ro`:
   - **Left side:** the folder on your computer that holds your manga.
   - **Right side:** the path from "Before you start", step 1. The default is `/var/manga`; change it if your old path was different, for example `- /srv/manga:/manga:ro`.

6. **Replace the old secret key.** Configs created by the original version contain `SECRET_KEY='REPLACE ME'`, which lets anyone forge a login. In `data/config/config.toml`, set it to a random value:

   ```sh
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

   This logs everyone out of the classic interface once. You can also delete the unused `DATABASE_FILE` line.

7. **Start the new version**, from the project folder:

   ```sh
   ls data/db/database.db data/config/config.toml    # both must exist here, or the server starts empty
   docker compose up -d
   docker compose logs -f
   ```

   This downloads the published image (`ghcr.io/xzcutable/mangalib`). To build it from the project folder instead, use `docker compose -f compose.yml -f compose.build.yml up -d --build`.

   If `ls` can't find them, step 2 ran in another folder. Move that `data` folder into the project folder first.

   The first start prints `Adding column manga.release_year`, `Adding column manga.last_updated` and `Found release years for N manga`. A warning about `SECRET_KEY` means step 6 didn't take effect.

8. **Check it**, using the checklist below. Then remove the old container: `docker rm <container>`.

From now on, your data lives in `./data` and survives updates. Back that folder up.

Later versions install from **Settings → Server updates** (see "Updating" in the [README](README.md#updating)), or with `docker compose pull && docker compose up -d`.

**Coming from a 1.2.0 setup that built its own image** (`build: .` in `compose.yml`)? After `git pull`, `compose.yml` uses the published image instead. Run `docker compose pull && docker compose up -d`; your `./data` folder is used as before.

---

## Without Docker (Python install)

1. **Stop the server.**
2. **Back up the database and config.**
   - The database is at `DATABASE_PATH` from your config. Without it, look for `instance/database.db` in the project folder (or the instance path printed at start-up).
   - The config is `config.toml` in the same instance folder, unless you set `CONFIG_PATH`.
3. **Update:**

   ```sh
   git pull
   pip install -r requirements.txt     # adds Flask-Cors
   pip install -e .                    # only if you installed the package before
   ```

   Python 3.11 or newer is required.
4. **Replace the old secret key**, as in Docker step 6, if your config still has `SECRET_KEY='REPLACE ME'`.
5. **Start the server** as before. Its first start prints the same database messages as in Docker step 7.
6. **Optional: switch to the new interface.** Without this, the classic interface stays at `/` and the app and API work alongside it.
   1. Build it with Node 22 and pnpm: `cd manga-site && pnpm install && pnpm build`.
   2. Set `FRONTEND_PATH` in `config.toml` to the built `manga-site/dist` folder.
   3. Restart. The classic interface moves to `/classic/`.
7. **Check it**, using the checklist below.

**Reverse proxy:** no changes are needed. The new interface and the API (`/api/v1`) are served from the same address as before.

---

## Check the upgrade

- [ ] You can log in with your existing account at `/` (or `/classic/`).
- [ ] The library lists the same manga, with covers. If every series is listed twice, the library path changed: see Troubleshooting.
- [ ] A manga you were reading resumes on the right chapter and page.
- [ ] Favorites, queue and tags are still there.
- [ ] Settings → Library shows your old library folder.
- [ ] Optional: the Android app connects to `http://<server>:5000` and logs in.

## Troubleshooting

- **Pages or covers don't load.** The server sees the manga at a different path than before. Make the right side of the `compose.yml` mount (or the folder location) match the old library path, then restart.
- **Every series is listed twice.** The library was scanned again from a new path. Roll back the database (below), fix the path, and start again.
- **`no configuration file provided: not found`.** `docker compose` was run outside the project folder. `cd` into the folder with `compose.yml` and run it again.
- **"Database not found … Creating the database."** The server didn't find your copied database, so it started an empty one. Check the database file is at `data/db/database.db` (Docker) or at your `DATABASE_PATH`.

## Rolling back

1. Stop the new version.
2. Put your backed-up database and config back. The upgraded database also still works with the old version; the extra tables and columns are ignored.
3. Start the old container again (`docker start <container>`) or check out the old commit (`git checkout 41d5c34`).

An old image can't be rebuilt today. To build one anyway:
- change `apt upgrade` to `apt upgrade -y` in the old Dockerfile;
- add `SQLAlchemy<2.1` to the old `requirements.txt`.
