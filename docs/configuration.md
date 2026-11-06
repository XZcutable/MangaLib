# Configuration

myMangaLib reads its settings from three places. Later ones win:

1. **`config.toml`**: made on first start, with a random secret key. In Docker it's in `/data/config.toml` (Compose: `./data/config.toml`).
2. **Flags or environment variables**: any `config.toml` key can be set as a `FLASK_<KEY>` environment variable (for example `FLASK_SITE_NAME`), and the common ones as flags (below).
3. **Settings the owner changes in the app** (site name, sign-ups, update checks). These are saved in the database and win over both.

## Flags

Anything after the image name in `docker run` is a flag, and `mymangalib serve` takes the same ones. `docker run --rm ghcr.io/xzcutable/mangalib --help` (or `mymangalib --help`) lists them.

| Flag | What it does |
|---|---|
| `--site-name NAME` | Name in the browser tab and the app |
| `--allow-new-users` / `--no-allow-new-users` | Let people create accounts |
| `--auto-approve-users` | New accounts can read without waiting for an admin |
| `--no-auto-update` | Don't check for or download updates on its own (the owner can still check in Settings) |
| `--update-check-hours N` | How often to check for updates (default 6) |
| `--url-prefix /manga` | Served at a sub-path by a reverse proxy (see [reverse-proxy.md](reverse-proxy.md)) |
| `--behind-proxy` / `--no-behind-proxy` | Trust `X-Forwarded-*` headers (on in the image) |
| `--cors-origins URL,URL` | Web pages allowed to call the API from a browser |
| `--library PATH` | A library folder to add on first start (the image already uses `/var/manga`) |
| `--library-moved OLD=NEW` | A library folder now mounted at `NEW` instead of `OLD`; the manga keep their reading progress (see [library.md](library.md#moving-the-library)) |
| `--port N`, `--host ADDR`, `--threads N` | Where and how the server listens |

## Data folder

`config.toml`, the database, the cover cache, downloaded updates and database backups are all in `/data` in Docker (Compose keeps it in `./data`). Back that folder up; replacing the container doesn't touch it. Containers set up with the older `/var/db` and `/var/config` volumes keep using them; see [UPGRADING.md](../UPGRADING.md#one-data-folder) to switch.

## Updates

The server checks GitHub for new versions every few hours and downloads them in the background. Nothing changes until the owner opens **Settings → Server updates** and clicks **Apply and restart**. The server then backs up the database and restarts into the new version, which takes under a minute. People using the site see an "updating" screen and land back on their page. If the new version doesn't start, the server goes back to the old one and restores the backup.

You can also update the image yourself: `docker pull ghcr.io/xzcutable/mangalib` and recreate the container (Compose: `docker compose pull && docker compose up -d`). Updates installed from Settings are kept in the data volume, and a newer image always wins over them.

Applying an update from Settings only works when the server was started with `mymangalib serve` (the Docker image does this). Under `flask run` or plain `waitress-serve` it can check and download, but not apply.

## Changing the site name

The site is called "myMangaLib" by default. The name appears in the browser tab, on the login screen and at the bottom of every page, in both interfaces.

**As the owner, in the app:** Settings → Library → Display → **Site name**, then **Save**. It takes effect straight away for everyone and is kept after restarts. Leave it empty to go back to the default.

**In the config:** set `SITE_NAME` in `config.toml` (or `--site-name` / `FLASK_SITE_NAME`), then restart:

```toml
SITE_NAME='My Manga'
```

This is the starting name; a name saved in Settings wins over it.

**In the code**, to change the default for everyone who builds from your copy:

| What | Where |
|---|---|
| Default name on the server | `DEFAULT_SITE_NAME` in `mymangalib/server/server_settings.py`, and `SITE_NAME` in `DEFAULT_CONFIG` in `mymangalib/constants.py` (written into new configs) |
| Tab title before the app has reached the server | `<title>` in `manga-site/index.html`, and `DEFAULT_SITE_NAME` in `manga-site/src/app/context/AuthContext.jsx` |
| Name under the Android app's icon | `appName` in `manga-site/capacitor.config.json` and `app_name` in `manga-site/android/app/src/main/res/values/strings.xml` |

Changes to `manga-site` take effect after rebuilding: `docker compose -f compose.yml -f compose.build.yml up -d --build` for Docker, or `pnpm build` in `manga-site/`. The Android app picks them up in its next release.

Don't change `"name": "myMangaLib"` in `server_info()` in `mymangalib/blueprints/api_v1.py`. The app checks it to recognize a myMangaLib server. If it changes, the app refuses to connect.

## Serving the new interface without Docker

Set `FRONTEND_PATH` in `config.toml` (or `FLASK_FRONTEND_PATH`) to the built front end, for example `manga-site/dist` after running `pnpm build` in `manga-site/`. The server then shows the new interface at `/` and moves the classic one to `/classic/`. Leave it empty to keep the classic interface at `/`. The Docker image does this for you.
