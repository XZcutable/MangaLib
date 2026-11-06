@AGENTS.md

# Notes for this project (local development)

AGENTS.md has the basics. Project-wide rules (commits, secrets, backend) are in `../CLAUDE.md`.

## Toolchain (Windows)
- pnpm is pinned with `"packageManager": "pnpm@10.34.3"`. The global pnpm is 12, which fails with `ERR_PNPM_VERIFY_DEPS_BEFORE_RUN`; the pin makes it switch automatically.
- Dev: `pnpm dev` at http://localhost:8443. Vite proxies `/api` to `http://127.0.0.1:5000`; override with `MANGALIB_SERVER`.
- Android SDK: `%LOCALAPPDATA%\Android\Sdk` (`platform-tools/adb.exe`, `emulator/emulator.exe`). adb isn't on PATH.
- In Git Bash, set `MSYS_NO_PATHCONV=1` before adb commands, or paths like `/sdcard/...` get rewritten. With it set, local paths for `adb pull` must be Windows-style (`C:/Users/...`), not `/c/Users/...`.
- Phone screenshots: `adb shell screencap -p /sdcard/s.png`, then `adb pull`. Redirecting `adb exec-out screencap` in PowerShell corrupts the PNG.
- Under pnpm, call `android/gradlew.bat` by its full path; Windows won't run it by bare name.
- VS Code's Java errors in `android/` (e.g. `getContext()` not found) are false positives: the editor has no Gradle classpath. Build with Gradle to check.
- `npx cap sync` rewrites line endings in `android/app/capacitor.build.gradle` and `android/capacitor.settings.gradle`. That diff is noise.

## App structure
- `src/app/lib/api.js`: API client; adds the token, parses JSON errors, `parseServerDate`. `lib/storage.js`: Capacitor Preferences in the app, localStorage on the web. `lib/native.js`: back button, keep-awake.
- `src/app/context/AuthContext.jsx`: server and login state. `loggedOutOnPurpose` prevents a login redirect loop; admins poll `/auth/me` every 30 s.
  - Saved servers: Preferences key `servers` (`[{ url, token, username, siteName }]`, most recent first; url `""` = the site the web app came from). `server`/`token` still hold the current one, so an older app version keeps its login. `switchServer` / `forgetServer` / `connect` (switches if the address is already saved with a login). Logging out keeps the server in the list.
  - UI: Settings → Servers (`settings/ServersSection.jsx`, app only, or on the web once another server is added), "Switch server" in the account menu, the saved list on the connect screen. `/connect` with state `{ addServer: true }` adds one while logged in.
- `src/app/components/settings/*`: owner/admin settings. `SettingSwitch` shows the disabled state and keeps its layout fixed.
- Show the site name with `siteName` from `useAuth()` (the owner's `site_name`), never a hard-coded "myMangaLib". The only fixed "myMangaLib" is the server check in `connect()`.
- `RequireAuth` shows `ChooseUsername` instead of the app while `user.must_change_username` is set. `api.js` flips it on when any request returns `username_change_required`.
- Accent colors: use `brand-*` classes (never `blue-*`); values per accent in `styles/brand.css`, picked in Settings → Appearance (`ThemeContext`). The default accent, "tenma", is taken from the mascot and also tints Tailwind's grays. The favorite heart uses `heart` (`fill-heart`).
- Mascot (Tenma): art is in `../Tenma/` (`Tenma.png` = main pose, approved poses as `<pose>.png` beside it (or in `source/`), prompts in `poses.toml`). `pnpm tenma:assets` turns it into `src/assets/tenma/*.webp`, the favicon and the Android icons/splash. Show her with `<Tenma pose="...">` (`components/Tenma.jsx`); missing poses fall back to the main one. `TenmaBackdrop` is the faint background figure (switch in Appearance). Drafts: `../scripts/tenma_drafts.py` (OpenAI API); nothing generated ships until it's copied into `../Tenma/`.
- Reader modes: paged or vertical scroll (`components/VerticalReader.jsx`). "Auto" uses the series' `reading_hint` (webtoon format/genre), then page shape (median height/width ≥ 2), cached per series in localStorage. Direction is per series, falling back to the hint, then the global setting.
- Offline downloads (Android only): `lib/offline.js` + `context/DownloadsContext.jsx` keep a per-server manifest in Preferences; native `OfflinePlugin`/`OfflineDownloader`/`DownloadService` (foreground service, dataSync) fetch pages to `filesDir/offline`. The manifest also keeps a trimmed copy of the series details (`savedInfo`, refreshed by `refreshInfo` whenever the series page loads online). Downloads is a cover grid (like Favorites); a cover opens the series page. Offline, `RequireAuth` allows only `/downloads`, `/manga/:id` of a downloaded series and `/read/*`; `MangaInfo` then uses `offline.offlineManga()` and opens only downloaded chapters. Progress is queued and sent on reconnect.
- Page size in paged mode (`lib/pageFit.js`): Smart fit (default), Fit screen, Fit width, Fit height; one global choice in `readerPageFit`, picked from the reader's menu or Settings → Reading. The old `readerFit` key is read once as a fallback (`width` stays Fit width, anything else becomes Smart fit). Smart fit shows the whole page, but fills the width and scrolls for long strips or when the whole page would be under 500 px tall. Sizes come from the image's shape, never its pixel count. Fit height pages scroll sideways; swipes and arrow keys scroll to the edge before turning.
- Navigation and icons follow the classic UI (`components/Navbar.jsx`). The reader (`pages/Reader.jsx`) has edge tap zones with a glow, swipe-follow, and page/chapter pickers.

## Android app
- `capacitor.config.json` uses `androidScheme: "http"` plus cleartext. With `https`, the WebView upgrades image requests and covers fail on plain-HTTP home servers. Don't change it.
- Emulator: AVD `MyMangaLib` (a Galaxy S24+ copy, this project's own). Never use `Galaxy_S24`: another project uses it and saves its own state into its quick-boot snapshot. Start it detached, or it's killed when the command ends: PowerShell `Start-Process "$env:LOCALAPPDATA\Android\Sdk\emulator\emulator.exe" -ArgumentList "-avd MyMangaLib -no-audio -no-boot-anim"`. From the emulator, the host's server is `10.0.2.2:5000`.
- Gradle needs `ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk` (there's no `local.properties`).
- The user's phone: Samsung SM-S926U, adb serial `R5CX6300EQX`. It runs release builds from GitHub.
- Signing: debug and release builds use different keys, so a debug install can't update a release install (or the reverse). Switching needs `adb uninstall com.mymangalib.app`, which wipes the saved server and login.
- UI checks: debug builds expose the WebView for Chrome DevTools (`adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>`, then playwright-core `connectOverCDP`). Release builds don't, so use `adb shell uiautomator dump` and `adb shell input tap`.

## Versions, releases and the auto-updater
- `package.json` `version` drives Android `versionName`; `versionCode` = major*10000 + minor*100 + patch, so minor and patch go up to 99 (`android/app/build.gradle`).
- Release signing reads `~/.mymangalib/release.properties` (or `MYMANGALIB_SIGNING`). Without it, `assembleRelease` produces an unsigned APK.
- Publish: `pnpm release X.Y.Z --notes "..."` or `--notes-file f.md`; `--dry-run` only builds into `release/` (gitignored). `../scripts/release.mjs` (repo root):
  1. Checks the token and that the tag is new.
  2. Bumps `package.json` and builds.
  3. Makes a draft release, uploads the APK, then publishes it (or deletes the draft on failure).

  Commit the version bump afterwards. The token comes from `GITHUB_TOKEN` or `~/.mymangalib/github-token` (fine-grained, Contents read/write on XZcutable/MangaLib); `MYMANGALIB_RELEASE_REPO` overrides the repo.
- Update flow:
  1. `lib/updater.js` reads `GET https://api.github.com/repos/XZcutable/MangaLib/releases/latest` (sends CORS `*`; a 404 means no releases).
  2. It compares the release with `App.getInfo()` and verifies the download against the asset's `digest` (`sha256:...`).
  3. `context/UpdateContext.jsx` checks 4 s after start and on resume, at most every 6 h; the user can skip a version. UI: `components/UpdateDialog.jsx` and `settings/UpdatesSection.jsx`. Android only (`canSelfUpdate`).
- Native side: `android/.../ApkUpdaterPlugin.java`, registered in `MainActivity`.
  - Downloads to `cacheDir/updates`.
  - Before opening Android's installer through the FileProvider, it rejects the wrong package, a version that isn't newer (`not_newer`), or a different signer (`signature_mismatch`).
  - Needs `REQUEST_INSTALL_PACKAGES`; the first update sends the user to "Install unknown apps".
- Testing an update without publishing:
  1. Build with `VITE_UPDATE_URL` pointing at a local copy of the release JSON.
  2. Serve that JSON with an `Access-Control-Allow-Origin: *` header. Python's plain `http.server` doesn't send it, so the app silently sees no update.
  3. Install an older signed release first, then point the feed at a newer signed APK.
