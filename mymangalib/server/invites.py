"""Invite codes for joining the server, shared as a link or QR code (<server>/join?code=...).

What an invite allows is decided when it's used, from its creator's role at that moment:
- An admin's invite works even while registration is closed, and the new account is approved straight away.
- Anyone else's invite only works while registration is open, and follows the auto-approve setting.
So demoting an admin also downgrades the invites they already handed out.

Only a hash of the code is stored. The code itself is shown to its creator once.
"""
import hashlib, secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from flask import current_app
from sqlalchemy import select

from ..database import db
from ..enum import Access
from ..models import Invite, User

DEFAULT_DAYS = 7
MAX_DAYS = 30
MAX_USES = 100
# 9 random bytes = 12 characters: short enough for a small QR code, far too many to guess
CODE_BYTES = 9

# Why an invite can't be used
EXPIRED = "invite_expired"
USED_UP = "invite_used_up"
CLOSED = "registration_closed"

def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()

def _now() -> datetime:
    return datetime.now(timezone.utc)

def can_create(user: User) -> bool:
    """Admins can always invite. Everyone else only while registration is open."""
    return Access.fromString(user.role) >= Access.ADMIN or bool(current_app.config.get("ALLOW_NEW_USERS"))

def create(user: User, days: int = DEFAULT_DAYS, max_uses: Optional[int] = 1) -> tuple[Invite, str]:
    """Returns the invite and its code. The code can't be recovered later."""
    code = secrets.token_urlsafe(CODE_BYTES)
    now = _now()
    invite = Invite(created_by=user.id, code_hash=_hash(code), created=str(now),
                    expires=str(now + timedelta(days=days)), max_uses=max_uses)
    db.session.add(invite)
    db.session.commit()
    return invite, code

def find(code: str) -> Optional[Invite]:
    if not isinstance(code, str) or not code.strip():
        return None
    return db.session.scalar(select(Invite).where(Invite.code_hash == _hash(code.strip())))

def creator(invite: Invite) -> Optional[User]:
    return db.session.get(User, invite.created_by)

def made_by_admin(invite: Invite) -> bool:
    user = creator(invite)
    return user is not None and user.approved and Access.fromString(user.role) >= Access.ADMIN

def status(invite: Invite) -> str:
    """"active", or why it can't be used: expired, used up, or (for a non-admin's invite) registration closed."""
    if datetime.fromisoformat(invite.expires) <= _now():
        return EXPIRED
    if invite.max_uses is not None and invite.uses >= invite.max_uses:
        return USED_UP
    if not made_by_admin(invite) and not current_app.config.get("ALLOW_NEW_USERS"):
        return CLOSED
    return "active"

def rules(invite: Invite) -> tuple[bool, bool]:
    """(registration open, auto approve) for someone joining with this invite. Check status() first."""
    if made_by_admin(invite):
        return True, True
    return bool(current_app.config.get("ALLOW_NEW_USERS")), bool(current_app.config.get("AUTO_APPROVE_NEW_USERS"))

def use(invite: Invite, user: User):
    """Counts a use and records who invited the user. The caller commits, together with the new account."""
    invite.uses += 1
    user.invited_by = invite.created_by

def listed(user: User) -> list[Invite]:
    """The user's own invites. Admins see everyone's."""
    query = select(Invite).order_by(Invite.id.desc())
    if Access.fromString(user.role) < Access.ADMIN:
        query = query.where(Invite.created_by == user.id)
    return db.session.scalars(query).all()

def can_delete(user: User, invite: Invite) -> bool:
    return invite.created_by == user.id or Access.fromString(user.role) >= Access.ADMIN

def delete(invite: Invite):
    db.session.delete(invite)
    db.session.commit()

def delete_for_user(user_id: int):
    """When an account is deleted, its invites go with it. The caller commits."""
    db.session.query(Invite).filter(Invite.created_by == user_id).delete()

def as_json(invite: Invite) -> dict:
    user = creator(invite)
    return {
        "id": invite.id,
        "created_by": {"id": invite.created_by, "username": user.username if user else None},
        "created": invite.created,
        "expires": invite.expires,
        "max_uses": invite.max_uses,
        "uses": invite.uses,
        "status": status(invite),
        "approved_on_join": made_by_admin(invite) or bool(current_app.config.get("AUTO_APPROVE_NEW_USERS")),
    }
