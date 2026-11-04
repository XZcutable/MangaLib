# myMangaLib app

The new myMangaLib front end: a React app that runs in the browser and, through Capacitor, as an Android and iOS app. It talks to a myMangaLib server through the JSON API at `/api/v1`.

## Develop in the browser

1. Start the server from the repo root:

   ```sh
   flask --app mymangalib run --port 5000
   ```

2. In `manga-site/`:

   ```sh
   pnpm install
   pnpm dev
   ```

   Open http://localhost:8443. Vite forwards `/api` to `http://127.0.0.1:5000`. To use a different server, set the `MANGALIB_SERVER` environment variable before `pnpm dev`.

## Mobile app

```sh
pnpm app:android   # builds, syncs and opens Android Studio
pnpm app:ios       # same for Xcode (needs a Mac)
```

On first launch the app asks for the server address, for example `192.168.1.20:5000` or `https://manga.example.com`.

- **Android emulator:** use `10.0.2.2:5000` to reach a server on the same computer.
- **Plain HTTP:** both platforms allow it for home-network servers. The Android app runs as `http://localhost`; with `https`, the WebView would upgrade image requests to HTTPS and covers and pages would fail to load. HTTPS through a reverse proxy is recommended for anything reachable from the internet.
- **Before publishing to a store:** change `appId` in `capacitor.config.json`.

## Releases and app updates

Android APKs are published on [GitHub Releases](https://github.com/XZcutable/MangaLib/releases). The app checks there when it opens (at most every 6 hours, or from Settings → App updates). When it finds a newer version, it shows the release notes and does the rest after you tap **Update**:

1. It downloads the APK and checks it against GitHub's checksum.
2. It confirms the APK is signed with the same key as the installed app.
3. It opens Android's install screen.

The first update asks the user to allow "Install unknown apps" for myMangaLib.

### One-time setup

- **Signing key:** `~/.mymangalib/release.jks` and `~/.mymangalib/release.properties`. **Back this folder up.** Every release must be signed with this key. If it's lost, installed apps can't update and every user has to uninstall and reinstall.
- **GitHub token:**
  1. Create a fine-grained personal access token at github.com → Settings → Developer settings.
  2. Give it access to `XZcutable/MangaLib` only, with **Contents: Read and write**.
  3. Save it in `~/.mymangalib/github-token` or the `GITHUB_TOKEN` environment variable.

### Publishing a release

```sh
pnpm release 1.0.0 --notes "First release"
pnpm release 1.1.0 --notes-file notes.md
pnpm release 1.1.0 --dry-run      # build the signed APK into release/ without publishing
```

The script does the following:

1. Checks the version isn't lower than the one in `package.json` and hasn't been published yet.
2. Sets that version.
3. Builds the web app and a signed release APK.
4. Creates the GitHub release as a draft, uploads the APK, and publishes it only once the upload succeeds.

Commit the `package.json` version change afterwards. Versions are `major.minor.patch`, with minor and patch up to 99; Android's version code is built from them (1.2.3 → 10203).

To test an update before publishing, build with `VITE_UPDATE_URL` pointing at a copy of the GitHub release JSON. The app then checks there instead of GitHub.

## How it fits together

| Path | What it does |
|---|---|
| `src/app/lib/api.js` | API client. Adds the login token. Image URLs carry it as `?t=`. |
| `src/app/lib/storage.js` | Saved server and token. Uses native storage in the app and localStorage on the web. |
| `src/app/context/AuthContext.jsx` | Server connection and login state. |
| `src/app/hooks/useMangaList.js` | Paged lists and search with infinite scroll. |
| `src/app/pages/Reader.jsx` | Reader: tap zones, swipes, arrow keys, right-to-left mode, saves progress. |

## Server settings that affect the app

The server's `config.toml` has a `CORS_ORIGINS` setting. It lists the web pages allowed to call `/api/v1` from a browser.

- The app's own origins are allowed by default: `capacitor://localhost` on iOS and `http://localhost` on Android.
- If you host this front end on a different domain from the server, add that domain to the list.
