# Changelog

What changed in each release of myMangaLib (the server and the app share a version).

New entries go under **Unreleased**, written for the people using the app. `pnpm release X.Y.Z` turns that
section into the release notes on GitHub and starts a new empty one. Use `###` for headings inside a version.

## Unreleased

## 1.10.0 (2026-11-09)

### Feedback

- **Send feedback from the app.** Report a bug, suggest an idea for the app or server, request a series, or report a problem with one, from the new Feedback page (Settings → Feedback), a series page or the reader.
- **Bug reports can include screenshots** (up to 3) and the app's recent log, so problems are easier to track down. The server's recent errors are attached too.
- **Feedback inbox for owners.** Settings → Feedback lists everything people sent, and the navbar badge counts items waiting for a reply. Admins see series requests and problems.

### Fixes

- New series found in the same scan are added in name order.

## 1.9.0 (2026-11-06)

Smarter search.

- Filters with suggestions as you type: `tag:fantasy|action` (either), `tag:fantasy&action` (both), `tag:"slice of life"`.
- `nsfw:` searches NSFW tags; `-nsfw` hides everything NSFW.
- `language:english|japanese` (English, Japanese, Korean, Chinese, Spanish, AI Translated, Mixed).
- `is:unread`, `is:read`, `is:progress`, `is:tagged`, `is:untagged`.
- A leading `-` excludes (`-tag:romance`, `-word`); `"double quotes"` match a phrase. Title search ignores case, accents included.
- A series' language is now picked from a list; existing values are converted when the server starts.
- The old `!tag:` and comma syntax is replaced by the above.

## 1.8.0 (2026-11-06)

### Sharing

- **Share your server with a QR code.** Open the account menu → Share. People scan it with their phone's camera, or with the app, to log in or join.
- **Invite links.** While sign-ups are open, anyone can invite people. Admins can invite people even when sign-ups are closed, and those accounts are approved straight away. Invites expire after 1 to 30 days, work for a set number of people, and can be cancelled.
- **Public address.** Owners can set the address people use from outside (Settings → Users → Public address), so invite links and QR codes work away from your home network.

### Android app

- **Scan a QR code** on the connect screen to add a server or accept an invite. Invite links opened in a phone's browser can open straight in the app.
- **Share the app without internet.** Settings → Share the app sends it to a nearby phone with Quick Share, Bluetooth or any other app.
- **Install from a file.** Checks an app file someone sent you before installing it. Official updates install as usual. Builds that aren't official show a warning first.
- **Back up and restore** your settings and saved servers (Download/myMangaLib). Logins aren't included, so you sign in again after restoring.

## 1.7.0 (2026-11-06)

App lock: Settings → App lock can hide the app behind your face, fingerprint or screen lock when it opens or comes back from the background (right away, or after 1, 5 or 15 minutes). "Hide in recent apps" blanks the app's preview in the app switcher. Android app only.

## 1.6.1 (2026-11-06)

### Fixes

- **Installing the web app behind a login proxy.** On servers behind a login such as Cloudflare Access, browsers couldn't install the web app. They can now.
- **Download menu on small screens.** On a series page, the Download menu no longer runs off the edge of the screen.

On iPhone, browsers never show an install prompt: use Share → Add to Home Screen.
