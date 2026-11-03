"""API login tokens. The raw token is shown to the client once; only its SHA-256 hash is stored."""
import hashlib, secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select

from ..database import db
from ..models import ApiToken, User

# Writing last_used on every request would mean a database write per image, so it's only refreshed this often
LAST_USED_RESOLUTION = timedelta(minutes=5)

def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def create_token(user: User, name: str = "") -> str:
    raw_token = secrets.token_urlsafe(32)
    now = str(datetime.now(timezone.utc))
    db.session.add(ApiToken(user_id=user.id, token_hash=_hash(raw_token), name=(name or "")[:100], created=now, last_used=now))
    db.session.commit()
    return raw_token

def find_token(raw_token: str) -> Optional[ApiToken]:
    if not raw_token:
        return None
    token: ApiToken = db.session.scalar(select(ApiToken).where(ApiToken.token_hash == _hash(raw_token)))
    if token is not None:
        now = datetime.now(timezone.utc)
        if token.last_used is None or now - datetime.fromisoformat(token.last_used) > LAST_USED_RESOLUTION:
            token.last_used = str(now)
            db.session.commit()
    return token

def user_tokens(user_id: int) -> list[ApiToken]:
    return db.session.scalars(select(ApiToken).where(ApiToken.user_id == user_id).order_by(ApiToken.id)).all()

def revoke(token: ApiToken):
    db.session.delete(token)
    db.session.commit()
