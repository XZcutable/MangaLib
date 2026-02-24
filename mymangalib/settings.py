from flask import (
    Blueprint, g, render_template, Flask
)
from .models import db, Path

from .auth import get_role_context

bp = Blueprint('settings', __name__, url_prefix='/settings')

def init_app(app: Flask):
    pass

@bp.route("")
def index():
    return render_template('settings/index.html', **get_role_context())

def getPaths() -> list[str]: 
    return [path[0] for path in Path.query.values(Path.path)]

def addPath(path):
    existingPath = Path.query.filter_by(path=path).one_or_none()

    if existingPath is None:
        path = Path(path=path)
        db.session.add(path)
        db.session.commit()
        return True
    return False

def removePath(path):
    query = Path.query.filter_by(path=path)
    if query.one_or_none() is None:
        return False
    else:
        query.delete()
        db.session.commit()
        return True