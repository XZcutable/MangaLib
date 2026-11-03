# Builds the new front end (manga-site). Only the built files go into the final image.
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
RUN npm install -g pnpm@10
COPY manga-site/package.json manga-site/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY manga-site/ ./
RUN pnpm build

FROM python:3.11-bookworm
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

RUN mkdir /var/db
RUN mkdir /var/manga
RUN mkdir /var/config

WORKDIR /mangalib
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

ENV FLASK_ENV_CONFIG=true \
FLASK_BEHIND_PROXY=true \
FLASK_CREATE_MISSING_CONFIG=true \
FLASK_CONFIG_PATH="/var/config/config.toml" \
FLASK_DATABASE_PATH="/var/db/database.db" \
FLASK_THUMBNAIL_CACHE_PATH="/var/db/covers" \
FLASK_FRONTEND_PATH="/mangalib/frontend"

# Mount these so data survives rebuilding the container (see compose.yml)
VOLUME ["/var/db", "/var/config"]

RUN mkdir /mangalib/mymangalib
COPY pyproject.toml pyproject.toml
COPY ./mymangalib /mangalib/mymangalib
RUN pip install .

# The new interface is served at /, the classic one at /classic/. Set FLASK_FRONTEND_PATH="" to keep the classic one at /.
COPY --from=frontend /build/dist /mangalib/frontend

EXPOSE 5000

# CMD ["flask", "--app", "mymangalib", "run", "--host=0.0.0.0"]
# CMD ["gunicorn", "-w", "2", "--bind=0.0.0.0:5000", "mymangalib:create_app()"]
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--call", "mymangalib:create_app"]