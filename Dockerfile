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

RUN mkdir /data /var/manga

WORKDIR /mangalib
# Dependencies first (from pyproject.toml), so a code change doesn't reinstall them
COPY pyproject.toml pyproject.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" \
    > /tmp/requirements.txt && pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

# PYTHONUNBUFFERED: the server's messages (scan results, warnings) show up in "docker compose logs" right away
# FLASK_DATA_DIR: config.toml, the database, covers and updates installed from Settings, all in one volume.
#   Containers made with the older /var/db + /var/config volumes keep using them (`mymangalib serve` checks).
ENV PYTHONUNBUFFERED=1 \
FLASK_HOST=0.0.0.0 \
FLASK_PORT=5000 \
FLASK_ENV_CONFIG=true \
FLASK_BEHIND_PROXY=true \
FLASK_CREATE_MISSING_CONFIG=true \
FLASK_DATA_DIR="/data" \
MYMANGALIB_DOCKER=1 \
FLASK_FRONTEND_PATH="/mangalib/frontend" \
FLASK_LIBRARY_PATHS='["/var/manga"]'

# Mount /data so data survives replacing the container (see compose.yml). The older /var/db and /var/config
# aren't declared any more: a volume mounted there was mounted on purpose, which is how the server spots it.
VOLUME ["/data"]

RUN mkdir /mangalib/mymangalib
COPY ./mymangalib /mangalib/mymangalib
RUN pip install .

# The new interface is served at /, the classic one at /classic/. Set FLASK_FRONTEND_PATH="" to keep the classic one at /.
COPY --from=frontend /build/dist /mangalib/frontend

EXPOSE 5000

ARG VERSION=dev
LABEL org.opencontainers.image.title="myMangaLib" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/XZcutable/MangaLib"

# `mymangalib serve` runs the server under a small supervisor that can restart it to apply updates.
# Anything after the image name is passed as flags, e.g.
#   docker run ... ghcr.io/xzcutable/mangalib --site-name "Home library" --no-auto-update
# (`docker run --rm ghcr.io/xzcutable/mangalib --help` lists them all.)
ENTRYPOINT ["mymangalib", "serve"]
CMD []