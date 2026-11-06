# Running behind a reverse proxy

The server works behind nginx, Caddy, Traefik and similar proxies, with or without HTTPS. Set `BEHIND_PROXY=true` in `config.toml` or `--behind-proxy` (the Docker image already does). Leave it off when the server is reached directly, so clients can't fake their address.

**Its own address** (`https://manga.example.com`): forward everything to the server. With nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 600s;
}
```

**A sub-path** (`https://example.com/manga/`): the new interface, the app and the classic interface all work there. Pick one of two setups:

- **The proxy removes `/manga`** (note the `/` at the end of `proxy_pass`) and says so with `X-Forwarded-Prefix`. Needs `BEHIND_PROXY=true`.

  ```nginx
  location /manga/ {
      proxy_pass http://127.0.0.1:5000/;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Prefix /manga;
      proxy_read_timeout 600s;
  }
  ```

- **The proxy passes `/manga/...` through unchanged** (no `/` at the end of `proxy_pass`). Tell the server with `URL_PREFIX='/manga'` in `config.toml` (`FLASK_URL_PREFIX=/manga` for Docker).

  ```nginx
  location /manga/ {
      proxy_pass http://127.0.0.1:5000;
      proxy_set_header Host $host;
      proxy_read_timeout 600s;
  }
  ```

In the Android app, the server address is the full one, e.g. `https://example.com/manga`. With either setup the server still answers on its own address too (e.g. `http://192.168.1.20:5000` at home).

Good to know:
- **`proxy_read_timeout`:** "Scan" in Settings waits until the scan is done. A first scan of a big library can take longer than nginx's default 60 seconds; the scan still finishes, but the page shows an error.
- **Pass the `Authorization` header** (most proxies do by default). The app logs in with it.
- **A proxy login in front of the server** needs `/api/v1/` left out of it (below).

## With a proxy login (basic auth, Authelia, Authentik, Cloudflare Access)
A login page in the proxy blocks the Android app: it can't fill in a browser login page or keep the proxy's cookie. Leave `/api/v1/` out of the proxy login, and keep the rest of the site behind it.

This is safe:
- **The server protects `/api/v1/` itself.** Everything there needs a myMangaLib login token, except checking that the server exists, logging in, and signing up (only when sign-ups are on).
- **The app only uses `/api/v1/`.**
- **The browser still needs the proxy login.** The web interface and the classic interface stay behind it, and the web interface's own API calls work as before.

Your proxy's setting for this:

- **nginx (basic auth):**

  ```nginx
  location / {
      auth_basic "Manga";
      auth_basic_user_file /etc/nginx/htpasswd;
      proxy_pass http://127.0.0.1:5000;
  }
  location /api/v1/ {
      auth_basic off;
      proxy_pass http://127.0.0.1:5000;
  }
  ```

- **Caddy:**

  ```caddy
  manga.example.com {
      @needs_login not path /api/v1/*
      basic_auth @needs_login {
          family <password hash from "caddy hash-password">
      }
      reverse_proxy 127.0.0.1:5000
  }
  ```

  For Authelia or Authentik, put the same `@needs_login` matcher on `forward_auth`.

- **Authelia:** a `bypass` rule above the site's other rules:

  ```yaml
  access_control:
    rules:
      - domain: manga.example.com
        resources: ['^/api/v1/']
        policy: bypass
      - domain: manga.example.com
        policy: one_factor
  ```

- **Authentik:** in the proxy provider, add `^/api/v1/` to **Unauthenticated Paths**.

- **Cloudflare Access:** add a second Access application for `manga.example.com/api/v1` with a policy whose action is **Bypass** (include: Everyone). The more specific path wins over the site's application.

- **Traefik:** a second router for `/api/v1` without the auth middleware:

  ```yaml
  - "traefik.http.routers.manga-api.rule=Host(`manga.example.com`) && PathPrefix(`/api/v1`)"
  - "traefik.http.routers.manga-api.priority=100"   # checked before the site's router, which has the auth middleware
  ```

With a sub-path, add it to the path (`/manga/api/v1/`).

