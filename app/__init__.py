from flask import Flask
from jinja2 import filters 

from . import api, auth, models, settings
from . import manga

import tomllib
from datetime import datetime, timezone

from werkzeug.middleware.proxy_fix import ProxyFix

BEHIND_PROXY = True

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    if BEHIND_PROXY:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_port=1, x_host=1, x_prefix=1
        )

    app.config.from_file(f'{app.root_path}/config.toml', load=tomllib.load, text=False)

    config_overrides(app)
    filters.FILTERS[tolocaltime.__name__] = tolocaltime

    manga.init_app(app)
    models.init_app(app)
    auth.init_app(app)
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

    return app

def config_overrides(app: Flask):
    app.config['HIDE_MANGA'] = False
    app.config['HIDE_TITLES'] = False
    pass

def tolocaltime(utc_time: datetime, format="%d/%m/%Y, %H:%M:%S"):
    if type(utc_time) == str:
        utc_time = datetime.fromisoformat(utc_time)
    return utc_time.astimezone().strftime(format)