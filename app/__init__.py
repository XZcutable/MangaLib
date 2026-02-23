from flask import Flask
from jinja2 import filters 

from .constants import ENV
from . import api, auth, models, settings
from . import manga

import tomllib
from datetime import datetime, timezone
import sys

from werkzeug.middleware.proxy_fix import ProxyFix

BEHIND_PROXY = True

config_path = None

def create_app():
    global config_path
    
    app = Flask(__name__, instance_relative_config=True)

    if BEHIND_PROXY:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_port=1, x_host=1, x_prefix=1
        )


    config_path = f'{app.root_path}/{ENV.CONFIG_NAME}'
    config_loaded = app.config.from_file(config_path, load=tomllib.load, text=False, silent=True)

    if not config_loaded:
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

        config_loaded = app.config.from_file(config_path, load=tomllib.load, text=False)
        # parse_args()
        # print(config_path)
        config_overrides(app)

    filters.FILTERS[tolocaltime.__name__] = tolocaltime

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


def config_overrides(app: Flask):
    # app.config['HIDE_MANGA'] = True
    # app.config['HIDE_TITLES'] = False
    pass

def tolocaltime(utc_time: datetime, format="%d/%m/%Y, %H:%M:%S"):
    if type(utc_time) == str:
        utc_time = datetime.fromisoformat(utc_time)
    return utc_time.astimezone().strftime(format)

def parse_args():
    global config_path
    args = sys.argv[1:]
    print(args)

    index = 0
    for arg in args:
        if arg.lower().startswith("--config"):
            temp = arg.split("=")
            if len(temp) == 1:
                index += 1
                path = args[index]
            else:
                path = temp[1]
            config_path = path

        index += 1