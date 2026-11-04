# MyMangaLibrary #
MyMangaLibrary is self hosted manga reading website. It aims to give users the features they expect from a manga reading websites while also keeping control of their data. It also strives to be flexible enough to allow a savy user to share their collections with others or customize their own experience without having to write the backend.

## Quick start with Docker ##
Needs Docker with Compose (Docker Desktop on Windows and macOS).

1. Clone the project. Put your manga in a `manga` folder next to `compose.yml`, or change `./manga` in `compose.yml` to where your manga already lives.
2. Start the server:

   ```sh
   docker compose up -d --build
   ```

3. Open http://localhost:5000 and create the owner account. Your manga is already there: the library folder is added and scanned on first start.

**Already running an older version?** Follow [UPGRADING.md](UPGRADING.md) first. The original Docker setup kept its database inside the container, so it has to be copied out before upgrading.

Notes:
- **Phones and other computers** connect to `http://<this computer's IP>:5000`, in a browser or in the Android app ([releases](https://github.com/XZcutable/MangaLib/releases)).
- **Data:** the database, cover cache and `config.toml` (with a random secret key) are kept in `./data`. Back it up; rebuilding or updating the container doesn't touch it.
- **Adding manga later:** copy it into the manga folder, then use Settings → Library → Scan.
- **Logs:** `docker compose logs -f` shows the first-start scan and any warnings.
- **Updating:** `git pull`, then `docker compose up -d --build`.
- **Classic interface:** still available at http://localhost:5000/classic/.

## Deployment or Development ##
To setup, first you must clone the project and have python installed. Some systems may use python3, but this will assume just 'python' will work. 

1\. While not technically necessary, it is recommened to first create a venv. To setup the venv environment run: <br>
`python -m venv .venv`

It is assumed the venv was created in the root directory of the project.

2\. Then activate the venv:
`.\.venv\Scripts\activate` on windows or `. .venv/bin/activate` for linux

3\. Then you need to install Flask and Flask-SQLAlchemy, this is why a venv is recommened:
`pip install -r requirements.txt`

4\. Finally run the server with a command like: <br>
`flask --app mymangalib run --host=0.0.0.0`

Depending on your needs, the command may be different.

To deploy, you'd follow the same steps except for the last one. You'd need to choose a [WSGI Server](https://flask.palletsprojects.com/en/stable/deploying/). The ones I tested are [Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/) and [Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/). But I find I perfer Gunicorn because it supports passing a string on startup, but waitress works if you don't need that.

The links explain how to install the server and application. But boils down to: <br>
> pip install \<server\>
<br>
 pip install -e .

Deployment commands would look something like:
> <b>Waitress:</b> <br>
waitress-serve --host=0.0.0.0 --port=5000 --call mymangalib:create_app

> <b>Gunicorn:</b> <br>
gunicorn -w 2 --bind=0.0.0.0:5000 'mymangalib:create_app()'

And then running the server with something like (for Linux): <br>
`(waitress-serve --host=0.0.0.0 --port=5000 mymangalib:app > /dev/null 2>&1 &)`

That will run the server in the background.

# Mobile app and new front end #
`manga-site/` holds the new front end. It runs in a browser and as an Android/iOS app. See [manga-site/README.md](manga-site/README.md).

It uses the JSON API under `/api/v1`, which logs in with tokens instead of cookies:

```sh
curl -X POST http://localhost:5000/api/v1/auth/login -H "Content-Type: application/json" \
     -d '{"username": "me", "password": "...", "device": "curl"}'
# -> {"token": "...", "user": {...}}
curl http://localhost:5000/api/v1/manga?list=all -H "Authorization: Bearer <token>"
```

Run the API tests with `pytest tests`.

## Serving the new interface ##
Set `FRONTEND_PATH` in `config.toml` (or the `FLASK_FRONTEND_PATH` environment variable) to the built front end, for example `manga-site/dist` after running `pnpm build` in `manga-site/`. The server then shows the new interface at `/` and moves the classic one to `/classic/`. Leave it empty to keep the classic interface at `/`.

The Docker image builds the front end and turns this on. Owners manage library folders, scanning, users and tags in the new interface under Settings; the classic interface stays available at `/classic/` in the meantime.

## Changing the site name ##
The site is called "myMangaLib" by default. The name appears in the browser tab, on the login screen and at the bottom of every page, in both interfaces.

**As the owner, in the app:** Settings → Library → Display → **Site name**, then **Save**. It takes effect straight away for everyone and is kept after restarts. Leave it empty to go back to the default.

**In the config:** set `SITE_NAME` in `config.toml` (or the `FLASK_SITE_NAME` environment variable), then restart:

```toml
SITE_NAME='My Manga'
```

This is the starting name; a name saved in Settings wins over it.

**In the code**, to change the default for everyone who builds from your copy:

| What | Where |
|---|---|
| Default name on the server | `DEFAULT_SITE_NAME` in `mymangalib/server/server_settings.py`, and `SITE_NAME` in `DEFAULT_CONFIG` in `mymangalib/constants.py` (written into new configs) |
| Tab title before the app has reached the server | `"title"` in `manga-site/.figma/make/site.json`, and `DEFAULT_SITE_NAME` in `manga-site/src/app/context/AuthContext.jsx` |
| Name under the Android app's icon | `appName` in `manga-site/capacitor.config.json` and `app_name` in `manga-site/android/app/src/main/res/values/strings.xml` |

Changes to `manga-site` take effect after rebuilding: `docker compose up -d --build` for Docker, or `pnpm build` in `manga-site/`. The Android app picks them up in its next release.

Don't change `"name": "myMangaLib"` in `server_info()` in `mymangalib/blueprints/api_v1.py`. The app checks it to recognize a myMangaLib server. If it changes, the app refuses to connect.

# Onboarding #
After the server is running, going to the url will take you to the simple onbaording process of making an Owner Account. After creating the account you will be taken to the login page. The home page will be empty but will select a random amount of registered titles when avaiable.

<details>
<summary><i>Screenshots</i></summary>

![Owner Creation](<screenshots/owner creation.png>)
![First View](screenshots/home.png)


</details>

# Adding Manga #
As the Owner, navigate to the settings. Under `Settings`, go to `Config`. Under `Local Paths`, click `Add Path`. A Folder Picker will pop up and you will navigate to the parent folder that holds all your manga. The path is now is now added. You can either start a scan by clicking `Scan Paths` or by clicking the Path and clciking `Ok` when prompted to rescan. If cancel is selected, you will be asked if you want to remove the Path.

<details>
<summary><i>Screenshots</i></summary>

![Settings](<screenshots/settings nav.png>)

![Config](screenshots/config.png)

![Select Path](<screenshots/select path.png>)

![Example](screenshots/example.png)

</details>

# Manga Structure #
THe structure for Manga is very easy. It starts with a folder in one of the paths you created and images inside of that folder or a subfolder. The ordering is the same way Windows Explorer does it. The current supported image types are ['.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif']. CBZ files are also supported and do not require a folder, but can be stored in one.

## Technical Requirements ##
This project aims to be as effcient and demand little of the host machine. It was developed and ran on a Raspberry Pi5 running Debian 12. That Pi5 was also hosting a Nginx server, a proxy, and HomeAssisant and suffered no performance issues. The application is constantly stress tested and performed smoothly with over a 1000 titles with 76,000 pages hosted on the device itself, external harddrive and remote network location. Python 3.11.2 was used when testing the application.

## Implemented Features ##
- CBZ, PDF, and ['.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif'] support
- User creation and login
- Manga progress
- Manga Tags
- Random Titles on homepage, Latest, All, Radmon and Unread
- Search title, tags and status (Needs doucmentation)