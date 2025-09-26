import os

from flask import Flask

from mangalib.blueprints import auth, manga, models, settings, api

import tomllib

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

    manga.init_app(app)
    models.init_app(app)
    auth.init_app(app)
    settings.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(manga.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(api.bp)


    app.add_url_rule('/', endpoint='manga.home')
    app.add_url_rule('/all', endpoint='manga.all')
    app.add_url_rule('/latest', endpoint='manga.latest')
    app.add_url_rule('/random', endpoint='manga.random')
    app.add_url_rule('/settings', endpoint='settings')
    app.add_url_rule('/search', endpoint='manga.search')

    return app

def config_overrides(app: Flask):
    app.config['HIDE_MANGA'] = False
    app.config['HIDE_TITLES'] = False
    pass