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
