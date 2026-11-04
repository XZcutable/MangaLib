"""Server settings the owner can change from the web interface.

config.toml (or FLASK_ environment variables) gives the starting value. Once the owner changes a
setting in the interface it's saved in the database and wins from then on, including after restarts.
"""
from flask import Flask, current_app

from ..database import db
from ..models import ServerSetting

# On/off settings: name in config.toml -> the name the API uses
EDITABLE = {
    "ALLOW_NEW_USERS": "allow_new_users",
    "AUTO_APPROVE_NEW_USERS": "auto_approve_new_users",
    "HIDE_MANGA": "hide_manga",
    "HIDE_TITLES": "hide_titles",
}
# Text settings, the same way
EDITABLE_TEXT = {
    "SITE_NAME": "site_name",
}

DEFAULT_SITE_NAME = "myMangaLib"
SITE_NAME_MAX_LENGTH = 40

# What config.toml said before saved settings were applied, so clearing a text setting can go back to it
_config_values: dict[str, str] = {}

def load(app: Flask):
    """Applies saved settings over the config file. Runs before anything reads them."""
    for key in EDITABLE_TEXT:
        _config_values[key] = app.config.get(key)
    with app.app_context():
        rows = db.session.query(ServerSetting).filter(ServerSetting.key.in_([*EDITABLE, *EDITABLE_TEXT])).all()
        for row in rows:
            app.config[row.key] = row.value if row.key in EDITABLE_TEXT else row.value == "true"

def get(key: str) -> bool:
    return bool(current_app.config.get(key, False))

def site_name() -> str:
    """The name shown in the browser tab and the interface. Not the "myMangaLib" the app checks for."""
    name = current_app.config.get("SITE_NAME")
    return name.strip() if isinstance(name, str) and name.strip() else DEFAULT_SITE_NAME

def set(key: str, value: bool):
    if key not in EDITABLE:
        raise KeyError(key)
    _save(key, "true" if value else "false")
    current_app.config[key] = value

    # The hide switches are also held by the manga views, which serve pages and covers
    from ..blueprints import manga
    if key == "HIDE_MANGA":
        manga.hide_content(value)
    elif key == "HIDE_TITLES":
        manga.hide_titles(value)

def set_text(key: str, value: str) -> str | None:
    """Saves a text setting. Empty goes back to the config.toml value. Returns an error message, or None."""
    if key not in EDITABLE_TEXT:
        raise KeyError(key)
    value = " ".join(value.split())  # No stray or repeated spaces
    if len(value) > SITE_NAME_MAX_LENGTH:
        return f"The site name can be up to {SITE_NAME_MAX_LENGTH} characters"

    if not value:
        row = db.session.get(ServerSetting, key)
        if row is not None:
            db.session.delete(row)
            db.session.commit()
        current_app.config[key] = _config_values.get(key)
    else:
        _save(key, value)
        current_app.config[key] = value
    return None

def _save(key: str, text: str):
    row = db.session.get(ServerSetting, key)
    if row is None:
        db.session.add(ServerSetting(key=key, value=text))
    else:
        row.value = text
    db.session.commit()

def as_json() -> dict:
    return {**{name: get(key) for key, name in EDITABLE.items()}, "site_name": site_name()}
