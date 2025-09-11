from flask import (
    Blueprint, g, render_template, Flask, current_app
)
from mangalib.blueprints.models import db, Path

from mangalib.lib.enum import Access

bp = Blueprint('settings', __name__, url_prefix='/settings')

def init_app(app: Flask):
    pass

@bp.route("")
def index():
    user_role = Access.fromString(g.user['role'])
    isOwner = user_role == Access.OWNER
    isAdmin = isOwner or user_role >= Access.ADMIN
    isMod = isAdmin or user_role >= Access.MODERATOR

    return render_template('settings/index.html', isOwner = isOwner, isAdmin = isAdmin, isMod = isMod)

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