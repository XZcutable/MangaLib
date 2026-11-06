# The JSON API

The new interface and the Android app talk to the server through a JSON API under `/api/v1`. It logs in with tokens instead of cookies, so you can use it from scripts too.

```sh
curl -X POST http://localhost:5000/api/v1/auth/login -H "Content-Type: application/json" \
     -d '{"username": "me", "password": "...", "device": "curl"}'
# -> {"token": "...", "user": {...}}

curl "http://localhost:5000/api/v1/manga?list=all" -H "Authorization: Bearer <token>"
```

- Send the token in the `Authorization: Bearer <token>` header. Image URLs in responses (`cover_url`, `image_url`) already carry it as `?t=<token>`, because an `<img>` tag can't send headers.
- Errors come back as `{"error": {"code": "...", "message": "..."}}` with a matching HTTP status.
- `GET /api/v1/server/info` needs no login and tells you the server's version and name.
- Each login is listed under **Settings → Devices**, where it can be signed out.
- To call the API from a web page on another address, add that address with `--cors-origins` (see [configuration.md](configuration.md)).

The routes are in `mymangalib/blueprints/api_v1.py` (users) and `mymangalib/blueprints/api_v1_admin.py` (owner and admins).
