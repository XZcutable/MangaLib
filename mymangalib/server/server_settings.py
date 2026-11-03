"""Server settings the owner can change from the web interface.

config.toml (or FLASK_ environment variables) gives the starting value. Once the owner changes a
setting in the interface it's saved in the database and wins from then on, including after restarts.
"""
from flask import Flask, current_app

from ..database import db
from ..models import ServerSetting

# Setting name in config.toml -> the name the API uses
EDITABLE = {
    "ALLOW_NEW_USERS": "allow_new_users",
    "AUTO_APPROVE_NEW_USERS": "auto_approve_new_users",
    "HIDE_MANGA": "hide_manga",
    "HIDE_TITLES": "hide_titles",
}

def load(app: Flask):
    """Applies saved settings over the config file. Runs before anything reads them."""
    with app.app_context():
        for row in db.session.query(ServerSetting).filter(ServerSetting.key.in_(EDITABLE)).all():
            app.config[row.key] = row.value == "true"

def get(key: str) -> bool:
    return bool(current_app.config.get(key, False))

def set(key: str, value: bool):
    if key not in EDITABLE:
        raise KeyError(key)
    row = db.session.get(ServerSetting, key)
    text = "true" if value else "false"
    if row is None:
        db.session.add(ServerSetting(key=key, value=text))
    else:
        row.value = text
    db.session.commit()
    current_app.config[key] = value

    # The hide switches are also held by the manga views, which serve pages and covers
    from ..blueprints import manga
    if key == "HIDE_MANGA":
        manga.hide_content(value)
    elif key == "HIDE_TITLES":
        manga.hide_titles(value)

def as_json() -> dict:
    return {name: get(key) for key, name in EDITABLE.items()}
