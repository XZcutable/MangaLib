# File structure

How the code and the server's data folders are laid out, what was fixed (November 2026), and what's left.

## Code (the repo)

```
mymangalib/          Python server (Flask)
  blueprints/        routes: api.py (old API), api_v1.py, api_v1_admin.py, manga.py, settings.py (classic UI)
  server/            shared logic: scanner.py, library_paths.py, move.py, server_settings.py, library.py, updater.py …
  templates/ static/ classic UI (Font Awesome: solid icons only, 4 files)
  cli.py supervisor.py child.py update_files.py version.py   launcher and update code
  queries.py models.py database.py auth.py …
manga-site/          React app (web + Android); plain Vite config
scripts/             release.mjs (`pnpm release` in manga-site runs it), make_server_bundle.py
tests/  screenshots/  compose*.yml  Dockerfile  pyproject.toml (the only dependency list)
```

### Fixed
- **Font Awesome** trimmed from about 5,700 files (43 MB) to 4 (232 KB). The classic UI loads `fontawesome.css` + `solid.css` and no longer loads the JS/SVG kit. The update bundle went from 7.5 MB to 0.7 MB.
- **Duplicate names:** `server/api.py` → `server/scanner.py`, `server/settings.py` → `server/library_paths.py`, `quries.py` → `queries.py`.
- **`.gitignore`** ignores `config.toml`, not every `*.toml`. This made `manga-site/.mise.toml` show up as untracked.
- **Release tooling** is all in `scripts/`.
- **Figma leftovers** removed. `vite.figma.config.js` had been the real build config: its settings (`base: "./"`, dev server, sourcemaps) are now in `vite.config.js`, and the title and meta tags it injected are written into `index.html`. `components/figma/ImageWithFallback.jsx` moved to `components/`. The build output is byte-identical.
- **Dependencies** are listed only in `pyproject.toml`. The Dockerfile installs from it, and the update bundle still ships a generated `requirements.txt`, because installed servers' updaters read it.

### Left as is
- **The launcher files sit loose in the package root.** Moving them into a subpackage needs a forwarding `mymangalib/child.py`, because already-installed supervisors start new versions through `mymangalib.child`. Not worth it yet.

## Data (on the server)

```
/data/                      one Docker volume (FLASK_DATA_DIR)
  config.toml
  database.db
  covers/                   cover cache
  updates/                  versions/ downloads/ backups/ state.json current …
/var/manga                  library (some installs mount it elsewhere)
```

Containers set up with the older `/var/db` + `/var/config` volumes, or with `./data/db` + `./data/config` from the old `compose.yml`, keep using them (`cli.docker_data_paths()`). UPGRADING.md explains how to switch.

### Fixed
- **One volume** instead of two.
- **The library can move.** `Manga.path` and `Chapter.path` are stored in full (pages keep only file names), so moving files used to make every manga "missing". Now:
  - A moved library folder is repointed from Settings → Library, or at startup with `--library-moved OLD=NEW` / `LIBRARY_MOVES`. Manga keep their ids, and so their reading data.
  - One series can be moved to another library folder from its Manage panel. The server moves the files as a job: a rename on the same disk, otherwise a hidden `.partial` copy, then a check, then the delete.

### Left as is
- **Paths are still absolute in the database.** Moves rewrite them (`library_paths.rewrite_prefix()`). Storing them relative to the library folder would make moves free, but it touches every file-opening code path, and every database would have to be converted once.
- **The cover cache sits next to the database.** It's disposable, but it's included when you back up `/data`.
