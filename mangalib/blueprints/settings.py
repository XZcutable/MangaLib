import json, os
from flask import (
    Blueprint, g, render_template, Flask, current_app
)
from mangalib.blueprints.db import db

from mangalib.lib.enum import Access

bp = Blueprint('settings', __name__, url_prefix='/settings')

CONFIG_FILE = 'config.json'

CONFIG = {}
PATHS = 'paths'

DEFAULT_CONFIG = {
    PATHS: []
}

def init_app(app: Flask):
    load_config_from_file()

@bp.route("")
def index():
    user_role = Access.fromString(g.user['role'])
    isOwner = user_role == Access.OWNER
    isAdmin = isOwner or user_role >= Access.ADMIN
    isMod = isAdmin or user_role >= Access.MODERATOR

    return render_template('settings/index.html', isOwner = isOwner, isAdmin = isAdmin, isMod = isMod)

def getConfig():
    return CONFIG

def getPaths() -> list[str]: 
    return CONFIG[PATHS]

def addPath(path):
    if path not in getPaths():
        getPaths().append(path)
        save_config()
        return True
    return False

def removePath(path):
    if path in getPaths():
        getPaths().remove(path)
        save_config()
        return True
    return False

def load_config_from_file():
    global CONFIG
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as file:
            json.dump(DEFAULT_CONFIG, file)
    else:
        with open(CONFIG_FILE, 'r') as file:
            CONFIG = json.load(file)
            
def save_config():
    with open(CONFIG_FILE, 'w') as file:
        json.dump(CONFIG, file)
    