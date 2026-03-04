FROM python:3.11-bookworm
RUN apt update; apt upgrade

RUN mkdir /var/db
RUN mkdir /var/manga
RUN mkdir /var/config

WORKDIR /mangalib
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

ENV FLASK_ENV_CONFIG=true \
FLASK_BEHIND_PROXY=true \
FLASK_CREATE_MISSING_CONFIG=true \
FLASK_CONFIG_PATH="/var/config/config.toml"

RUN mkdir /mangalib/mymangalib
COPY pyproject.toml pyproject.toml
COPY ./mymangalib /mangalib/mymangalib
RUN pip install .

EXPOSE 5000

# CMD ["flask", "--app", "mymangalib", "run", "--host=0.0.0.0"]
# CMD ["gunicorn", "-w", "2", "--bind=0.0.0.0:5000", "mymangalib:create_app()"]
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--call", "mymangalib:create_app"]