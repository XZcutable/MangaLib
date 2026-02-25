from flask import Flask
from jinja2 import filters 

from .constants import ENV
from . import api, auth, models, settings
from . import manga

import os, tomllib
from datetime import datetime, timezone

from werkzeug.middleware.proxy_fix import ProxyFix

def create_app(config_file=None):
    app = Flask(__name__, instance_relative_config=True)
    ENV.APP_ROOT_PATH = app.root_path
    ENV.APP_INSTANCE_PATH = app.instance_path
    os.makedirs(app.instance_path, exist_ok=True)

    if config_file is None:
        config_path = f'{app.instance_path}/{ENV.CONFIG_NAME}'
        config_loaded = app.config.from_file(config_path, load=tomllib.load, text=False, silent=True)
        if not config_loaded:
            create_default_config(config_path)
            config_loaded = app.config.from_file(config_path, load=tomllib.load, text=False)
    else:
        config_loaded = app.config.from_file(config_file, load=tomllib.load, text=False)

    if app.config["BEHIND_PROXY"]:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_port=1, x_host=1, x_prefix=1
        )

    create_filters()

    models.init_app(app)
    auth.init_app(app)
    api.init_app(app)
    manga.init_app(app)
    settings.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(manga.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(api.bp)

    app.add_url_rule('/manga/manga-image', endpoint='manga_image')
    app.add_url_rule('/manga', endpoint='manga')
    app.add_url_rule('/all', endpoint='manga.all')
    app.add_url_rule('/latest', endpoint='manga.latest')
    app.add_url_rule('/random', endpoint='manga.random')
    app.add_url_rule('/settings', endpoint='settings')
    app.add_url_rule('/search', endpoint='manga.search')

    @app.route('/')
    def index():
        return manga.home()
    
    app.add_url_rule('/', endpoint='manga.home')

    format="%b %d %Y at %I:%M %p"
    print(datetime.now(timezone.utc).strftime(format))
    print(datetime.now(timezone.utc).astimezone().strftime(format))

    with app.app_context():
        manga.update_manga_count()

    return app

def create_filters():
    def tolocaltime(utc_time: datetime, format="%d/%m/%Y, %H:%M:%S"):
        if type(utc_time) == str:
            utc_time = datetime.fromisoformat(utc_time)
        return utc_time.astimezone().strftime(format)

    filters.FILTERS[tolocaltime.__name__] = tolocaltime

def create_default_config(config_path: str):
    print(f"Config does not exist. Creating at {config_path}")
    with open(config_path, "w") as config:
        config.write(ENV.DEFAULT_CONFIG)
    
    should_exit = None
    while should_exit is None:
        should_exit = input("A default config was created. Would you like to edit the config? (y/n): ")
        if should_exit.lower() == "y":
            should_exit = True
        elif should_exit.lower() == "n":
            should_exit = False
        else:
            should_exit = None
    
    if should_exit:
        exit()