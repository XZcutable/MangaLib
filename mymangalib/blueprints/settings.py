from flask import (
    Blueprint, g, render_template, Flask
)
from ..server.library_paths import update_paths

from ..auth import get_role_context

bp = Blueprint('settings', __name__, url_prefix='/settings')

def init_app(app: Flask):
    with app.app_context():
        update_paths()

@bp.route("")
def index():
    return render_template('settings/index.html', **get_role_context())