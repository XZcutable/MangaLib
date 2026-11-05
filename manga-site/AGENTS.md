# Manga Site

The myMangaLib app: React + Vite + Tailwind CSS. It runs in the browser and, through Capacitor, as the Android app.

## Development Server

`pnpm dev` starts Vite on `$PORT` (default 8443) and forwards `/api` to a myMangaLib server at
`http://127.0.0.1:5000` (override with `MANGALIB_SERVER`). Nothing runs until you start it.

## Key Files

- `src/main.jsx` - Browser entry point
- `vite.config.js` - Build configuration (relative asset paths, app version, dev proxy)
- `index.html` - Page shell, including the default `<title>`
