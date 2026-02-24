# MyMangaLibrary #
MyMangaLibrary is self hosted manga reading website. It aims to give users the features they expect from a manga reading websites while also keeping control of their data. It also strives to be flexible enough to allow a savy user to share their collections with others or customize their own experience without having to write the backend.

## Deployment or Development ##
To setup, first you must clone the project and have python installed. Some systems may use python3, but this will assume just 'python' will work. 

1\. While not technically necessary, it is recommened to first create a venv. To setup the venv environment run: <br>
`python -m venv .venv`

It is assumed the venv was created in the root directory of the project.

2\. Then activate the venv:
`.\.venv\Scripts\activate` on windows or `. .venv/bin/activate` for linux

3\. Then you need to install Flask and Flask-SQLAlchemy, this is why a venv is recommened:
`pip install Flask Flask-SQLAlchemy`

4\. Finally run the server with a command like: <br>
`flask --app mymangalib run --host=0.0.0.0`

Depending on your needs, the command may be different.

To deploy, you'd follow the same steps except for the last one. You'd need to choose a [WSGI Server](https://flask.palletsprojects.com/en/stable/deploying/). The ones I tested are [Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/) and [Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/).

The links explain how to install the server and application. But boils down to: <br>
> pip install \<server\>
<br>
 pip install -e .

And then running the server with something like (for Linux): <br>
`(waitress-serve --host=0.0.0.0 --port=5000 mymangalib:app > /dev/null 2>&1 &)`

That will run the server in the background.

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