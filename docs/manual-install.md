# Installing without Docker

Needs Python 3.11 or newer. These commands use `python`; some systems call it `python3`.

1. **Get the code and make a virtual environment** in the project folder:

   ```sh
   git clone <this repository's URL> mymanga
   cd mymanga
   python -m venv .venv
   ```

2. **Activate it:** `.venv\Scripts\activate` on Windows, `. .venv/bin/activate` on Linux and macOS.

3. **Install the server** and its dependencies:

   ```sh
   pip install -e .
   ```

4. **Build the new interface** (optional; without it you get the classic interface). Needs Node.js and [pnpm](https://pnpm.io/):

   ```sh
   cd manga-site
   pnpm install
   pnpm build
   cd ..
   ```

   Then set `FRONTEND_PATH='manga-site/dist'` in `config.toml` (see [configuration.md](configuration.md#serving-the-new-interface-without-docker)).

5. **Start it:**

   ```sh
   mymangalib serve --host 0.0.0.0 --port 5000 --library /path/to/manga
   ```

   `python -m mymangalib serve ...` works too. It takes the same flags as the Docker image (`mymangalib --help`). Open `http://localhost:5000` and create the owner account.

## Other ways to run it

`mymangalib serve` is recommended: it runs the server with [Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/) and can install updates from Settings. Any WSGI server works if you don't need that:

```sh
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 --call mymangalib:create_app

pip install gunicorn          # Linux and macOS
gunicorn -w 2 --bind=0.0.0.0:5000 'mymangalib:create_app()'
```

To keep it running in the background on Linux, use a systemd service, or for a quick test:

```sh
(mymangalib serve --host 0.0.0.0 --port 5000 > /dev/null 2>&1 &)
```

## Hardware

The server asks little of the machine. It was developed on a Raspberry Pi 5 running Debian 12, alongside nginx and Home Assistant, and has been tested with over 1,000 titles and 76,000 pages stored on the Pi itself, an external drive and a network share.
