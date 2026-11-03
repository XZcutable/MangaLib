@AGENTS.md

# Notes for this project (local development)

AGENTS.md describes the Figma Make environment. Locally, no dev server is running until you start one. Project-wide rules (commits, secrets, backend) are in `../CLAUDE.md`.

## Toolchain (Windows)
- pnpm is pinned with `"packageManager": "pnpm@10.34.3"`. The global pnpm is 12, which fails with `ERR_PNPM_VERIFY_DEPS_BEFORE_RUN`; the pin makes it switch automatically.
- Dev: `pnpm dev` at http://localhost:8443. Vite proxies `/api` to `http://127.0.0.1:5000`; override with `MANGALIB_SERVER`.
- Android SDK: `%LOCALAPPDATA%\Android\Sdk` (`platform-tools/adb.exe`, `emulator/emulator.exe`). adb isn't on PATH.
- In Git Bash, set `MSYS_NO_PATHCONV=1` before adb commands, or paths like `/sdcard/...` get rewritten.
- Under pnpm, call `android/gradlew.bat` by its full path; Windows won't run it by bare name.
- VS Code's Java errors in `android/` (e.g. `getContext()` not found) are false positives: the editor has no Gradle classpath. Build with Gradle to check.
- `npx cap sync` rewrites line endings in `android/app/capacitor.build.gradle` and `android/capacitor.settings.gradle`. That diff is noise.

## App structure
- `src/app/lib/api.js`: API client; adds the token, parses JSON errors, `parseServerDate`. `lib/storage.js`: Capacitor Preferences in the app, localStorage on the web. `lib/native.js`: back button, keep-awake.
- `src/app/context/AuthContext.jsx`: server and login state. `loggedOutOnPurpose` prevents a login redirect loop; admins poll `/auth/me` every 30 s.
- `src/app/components/settings/*`: owner/admin settings. `SettingSwitch` shows the disabled state and keeps its layout fixed.
- Navigation and icons follow the classic UI (`components/Navbar.jsx`). The reader (`pages/Reader.jsx`) has edge tap zones with a glow, swipe-follow, and page/chapter pickers.

## Android app
- `capacitor.config.json` uses `androidScheme: "http"` plus cleartext. With `https`, the WebView upgrades image requests and covers fail on plain-HTTP home servers. Don't change it.
- Emulator: AVD `Galaxy_S24` (`emulator -avd Galaxy_S24 -no-audio -no-snapshot-save -no-boot-anim`). From the emulator, the host's server is `10.0.2.2:5000`.
- The user's phone: Samsung SM-S926U, adb serial `R5CX6300EQX`. It runs release builds from GitHub.
- Signing: debug and release builds use different keys, so a debug install can't update a release install (or the reverse). Switching needs `adb uninstall com.mymangalib.app`, which wipes the saved server and login.
- UI checks: debug builds expose the WebView for Chrome DevTools (`adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>`, then playwright-core `connectOverCDP`). Release builds don't, so use `adb shell uiautomator dump` and `adb shell input tap`.

## Versions, releases and the auto-updater
- `package.json` `version` drives Android `versionName`; `versionCode` = major*10000 + minor*100 + patch, so minor and patch go up to 99 (`android/app/build.gradle`).
- Release signing reads `~/.mymangalib/release.properties` (or `MYMANGALIB_SIGNING`). Without it, `assembleRelease` produces an unsigned APK.
- Publish: `pnpm release X.Y.Z --notes "..."` or `--notes-file f.md`; `--dry-run` only builds into `release/` (gitignored). `scripts/release.mjs`:
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
