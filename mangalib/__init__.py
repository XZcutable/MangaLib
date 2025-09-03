import os

from flask import Flask, g

from mangalib.blueprints import db, auth, manga, settings, api

import tomllib

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_file(f'{app.root_path}/config.toml', load=tomllib.load, text=False)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    auth.init_app(app)
    settings.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(manga.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(api.bp)

    app.add_url_rule('/', endpoint='home')
    app.add_url_rule('/manga', endpoint='manga')
    app.add_url_rule('/settings', endpoint='settings')

    return app