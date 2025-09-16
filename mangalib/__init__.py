import os

from flask import Flask

from mangalib.blueprints import auth, manga, models, settings, api

import tomllib

def create_app():
    app = Flask(__name__, instance_relative_config=True)
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


    app.add_url_rule('/', endpoint='home')
    app.add_url_rule('/all', endpoint='manga.all')
    app.add_url_rule('/latest', endpoint='manga.latest')
    app.add_url_rule('/manga', endpoint='manga')
    app.add_url_rule('/random', endpoint='manga.random')
    app.add_url_rule('/manga-image', endpoint='manga-image')
    app.add_url_rule('/settings', endpoint='settings')

    return app

def config_overrides(app: Flask):
    app.config["HIDE_MANGA"] = True
    app.config["HIDE_TITLES"] = True