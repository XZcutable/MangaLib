"""Feedback sent from the app: bug reports, app and server ideas, and content requests.

Who sees what:
- The person who sent it sees their own items, replies and status changes.
- Bugs and ideas (OWNER_KINDS) go to the owner only, with logs, screenshots and device details.
- Content requests and problems (CONTENT_KINDS) go to every admin, since they look after the library.

Statuses are shared with a planned agent worker (docs/feedback-agent.md). It will triage bugs and
ideas, post a plan, and leave the decision to the owner. STAFF_TRANSITIONS is what people can do
now; AGENT_TRANSITIONS is reserved for that worker and checked the same way.
"""
import json, os, secrets, shutil
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import current_app
from sqlalchemy import func, select

from ..database import db
from ..enum import Access
from ..models import Feedback, FeedbackAttachment, FeedbackEvent, Manga, User
from . import logbuffer

OWNER_KINDS = ("bug", "app_idea", "server_idea")
CONTENT_KINDS = ("content_request", "content_problem")
KINDS = OWNER_KINDS + CONTENT_KINDS

STATUSES = ("new", "triaging", "needs_info", "planning", "plan_ready", "changes_requested",
            "approved", "in_progress", "done", "declined", "duplicate")
CLOSED = ("done", "declined", "duplicate")
# Content items never go to the agent, so they only use these
CONTENT_STATUSES = ("new", "needs_info", "in_progress", "done", "declined", "duplicate")
# Waiting for the owner (or, for content, an admin): counted on the badge
WAITING = ("new", "plan_ready")

_HANDLED = {"needs_info", "approved", "in_progress", "done", "declined", "duplicate"}
STAFF_TRANSITIONS = {
    "new": _HANDLED,
    "triaging": _HANDLED | {"new"},
    "needs_info": _HANDLED - {"needs_info"} | {"new"},
    "planning": _HANDLED | {"new"},
    "plan_ready": {"approved", "changes_requested", "declined", "needs_info", "duplicate"},
    "changes_requested": {"approved", "declined", "new"},
    "approved": {"in_progress", "done", "declined"},
    "in_progress": {"done", "approved", "declined"},
    "done": {"new", "in_progress"},
    "declined": {"new"},
    "duplicate": {"new"},
}
AGENT_TRANSITIONS = {
    "new": {"triaging"},
    "triaging": {"needs_info", "declined", "duplicate", "planning"},
    "planning": {"plan_ready"},
    "changes_requested": {"planning", "plan_ready"},
}

MAX_SCREENSHOTS = 3
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
MAX_PER_DAY = 10
SERVER_LOG_SECONDS = 30 * 60
LIMITS = {"title": 150, "body": 10_000, "steps": 5_000, "expected": 2_000, "actual": 2_000, "comment": 5_000}
MAX_CLIENT_LOG = 200_000
MAX_CONTEXT = 4_000
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}

# --- Who can see and change what ---

def role(user: User) -> Access:
    return Access.fromString(user.role)

def is_staff_for(user: User, item: Feedback) -> bool:
    """Whether the user handles this item: the owner always, admins for content."""
    if role(user) == Access.OWNER:
        return True
    return role(user) >= Access.ADMIN and item.kind in CONTENT_KINDS

def can_view(user: User, item: Feedback) -> bool:
    return item.user_id == user.id or is_staff_for(user, item)

def kinds_for(user: User) -> tuple[str, ...]:
    """The kinds a user's inbox shows."""
    if role(user) == Access.OWNER:
        return KINDS
    if role(user) >= Access.ADMIN:
        return CONTENT_KINDS
    return ()

def allowed_statuses(item: Feedback, actor: str = "staff") -> list[str]:
    table = AGENT_TRANSITIONS if actor == "agent" else STAFF_TRANSITIONS
    allowed = table.get(item.status, set())
    if item.kind in CONTENT_KINDS:
        allowed = allowed & set(CONTENT_STATUSES)
    return [status for status in STATUSES if status in allowed]

# --- Files ---

def feedback_dir() -> str:
    path = current_app.config.get("FEEDBACK_PATH")
    if not path:
        database = current_app.config.get("DATABASE_PATH")
        base = os.path.dirname(os.path.abspath(str(database))) if database else current_app.instance_path
        path = os.path.join(base, "feedback")
    return str(path)

def image_type(head: bytes) -> Optional[str]:
    """The image's real type from its first bytes, or None. The file name and browser's type aren't trusted."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None

def read_screenshots(files) -> tuple[list[tuple[bytes, str]], Optional[str]]:
    """Checks uploads before anything is saved. Returns [(data, content_type)] or a problem."""
    if len(files) > MAX_SCREENSHOTS:
        return [], f"Attach at most {MAX_SCREENSHOTS} screenshots"
    images = []
    for upload in files:
        data = upload.read(MAX_SCREENSHOT_BYTES + 1)
        if len(data) > MAX_SCREENSHOT_BYTES:
            return [], f"Screenshots can be at most {MAX_SCREENSHOT_BYTES // (1024 * 1024)} MB each"
        content_type = image_type(data[:16])
        if content_type is None:
            return [], "Screenshots must be PNG, JPEG or WebP images"
        images.append((data, content_type))
    return images, None

def attachment_path(attachment: FeedbackAttachment) -> str:
    return os.path.join(feedback_dir(), str(attachment.feedback_id), attachment.file_name)

def _save_images(item: Feedback, images: list[tuple[bytes, str]]):
    folder = os.path.join(feedback_dir(), str(item.id))
    os.makedirs(folder, exist_ok=True)
    for data, content_type in images:
        name = secrets.token_hex(12) + IMAGE_TYPES[content_type]
        with open(os.path.join(folder, name), "wb") as file:
            file.write(data)
        db.session.add(FeedbackAttachment(feedback_id=item.id, file_name=name, content_type=content_type,
                                          size=len(data), created=db.getDatetimeISONow()))

# --- Reading ---

def attachments(item: Feedback) -> list[FeedbackAttachment]:
    return list(db.session.scalars(
        select(FeedbackAttachment).where(FeedbackAttachment.feedback_id == item.id).order_by(FeedbackAttachment.id)))

def events(item: Feedback) -> list[FeedbackEvent]:
    return list(db.session.scalars(
        select(FeedbackEvent).where(FeedbackEvent.feedback_id == item.id).order_by(FeedbackEvent.id)))

# Agent triage and plans are for the owner; the sender sees replies and status changes
SENDER_EVENT_KINDS = ("comment", "status")

def event_json(event: FeedbackEvent) -> dict:
    user = db.session.get(User, event.user_id) if event.user_id else None
    return {
        "id": event.id,
        "author": event.author,
        "username": user.username if user else None,
        "kind": event.kind,
        "body": event.body,
        "data": json.loads(event.data) if event.data else None,
        "created": event.created,
    }

def feedback_json(item: Feedback, viewer: User, attachment_url=None, detail: bool = False) -> dict:
    """attachment_url(item, attachment) makes the image link (the blueprint knows the route)."""
    sender = db.session.get(User, item.user_id)
    staff = is_staff_for(viewer, item)
    data = {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "status": item.status,
        "username": sender.username if sender else None,
        "mine": item.user_id == viewer.id,
        "manga_id": item.manga_id,
        "manga_title": item.manga_title,
        "chapter": item.chapter,
        "created": item.created,
        "updated": item.updated,
        "attachment_count": len(attachments(item)),
    }
    if not detail:
        return data
    data.update({
        "body": item.body,
        "steps": item.steps,
        "expected": item.expected,
        "actual": item.actual,
        "client_log": item.client_log,
        "attachments": [
            {"id": a.id, "content_type": a.content_type, "size": a.size,
             "url": attachment_url(item, a) if attachment_url else None}
            for a in attachments(item)
        ],
        "events": [event_json(e) for e in events(item) if staff or e.kind in SENDER_EVENT_KINDS],
    })
    if staff:
        data["context"] = json.loads(item.context) if item.context else None
        data["allowed_statuses"] = allowed_statuses(item)
        if role(viewer) == Access.OWNER:
            data["server_log"] = item.server_log
    return data

def list_for_user(user: User) -> list[Feedback]:
    return list(db.session.scalars(
        select(Feedback).where(Feedback.user_id == user.id).order_by(Feedback.id.desc())))

def inbox(user: User, kind: Optional[str] = None, status: Optional[str] = None) -> list[Feedback]:
    """status: one status, "open" (not closed) or None for everything. Oldest waiting items first."""
    kinds = kinds_for(user)
    if kind:
        kinds = tuple(k for k in kinds if k == kind)
    query = select(Feedback).where(Feedback.kind.in_(kinds))
    if status == "open":
        query = query.where(Feedback.status.not_in(CLOSED)).order_by(Feedback.id)
    elif status:
        query = query.where(Feedback.status == status).order_by(Feedback.id.desc())
    else:
        query = query.order_by(Feedback.id.desc())
    return list(db.session.scalars(query))

def pending_count(user: User) -> int:
    kinds = kinds_for(user)
    if not kinds:
        return 0
    return db.session.scalar(select(func.count()).select_from(Feedback)
                             .where(Feedback.kind.in_(kinds), Feedback.status.in_(WAITING)))

# --- Changes ---

def _text(body: dict, key: str, required: bool = False) -> tuple[Optional[str], Optional[str]]:
    value = body.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, (f"{key.replace('_', ' ').capitalize()} is required" if required else None)
    if not isinstance(value, str):
        return None, f"{key} must be text"
    value = value.strip()
    if len(value) > LIMITS[key]:
        return None, f"{key.capitalize()} can be at most {LIMITS[key]} characters"
    return value, None

def sent_today(user: User) -> int:
    since = str(datetime.now(timezone.utc) - timedelta(days=1))
    return db.session.scalar(select(func.count()).select_from(Feedback)
                             .where(Feedback.user_id == user.id, Feedback.created >= since))

def create(user: User, body: dict, files: list, server_context: dict) -> tuple[Optional[Feedback], Optional[str]]:
    """Validates and saves new feedback. Returns (item, None) or (None, problem)."""
    kind = body.get("kind")
    if kind not in KINDS:
        return None, f"kind must be one of: {', '.join(KINDS)}"

    fields = {}
    for key, required in (("title", kind != "content_problem"), ("body", kind == "bug"),
                          ("steps", False), ("expected", False), ("actual", False)):
        fields[key], problem = _text(body, key, required)
        if problem:
            return None, problem

    manga = None
    chapter = body.get("chapter")
    if kind == "content_problem":
        manga_id = body.get("manga_id")
        manga = db.session.get(Manga, manga_id) if isinstance(manga_id, int) and not isinstance(manga_id, bool) else None
        if manga is None:
            return None, "Pick the series this is about"
        fields["title"] = fields["title"] or f"Problem with {manga.title}"
    if chapter is not None and (isinstance(chapter, bool) or not isinstance(chapter, int)):
        return None, "chapter must be a chapter number"
    if kind != "bug":
        fields["steps"] = fields["expected"] = fields["actual"] = None

    client_log = body.get("client_log")
    if client_log is not None and not isinstance(client_log, str):
        return None, "client_log must be text"
    if client_log:
        # Keep the newest lines when it's too long
        client_log = logbuffer.redact(client_log[-MAX_CLIENT_LOG:])

    context = body.get("context")
    context = dict(context) if isinstance(context, dict) else {}
    context.update(server_context)
    context_text = json.dumps(context)[:MAX_CONTEXT]

    images, problem = read_screenshots(files)
    if problem:
        return None, problem
    if images and kind not in ("bug", "content_problem"):
        return None, "Screenshots can only be added to bug reports and content problems"

    if role(user) != Access.OWNER and sent_today(user) >= MAX_PER_DAY:
        return None, "too_many"

    now = db.getDatetimeISONow()
    item = Feedback(
        user_id=user.id, kind=kind, title=fields["title"], body=fields["body"] or "",
        steps=fields["steps"], expected=fields["expected"], actual=fields["actual"],
        manga_id=manga.id if manga else None, manga_title=manga.title if manga else None,
        chapter=chapter if manga else None, context=context_text,
        client_log=client_log or None,
        server_log=(logbuffer.recent(SERVER_LOG_SECONDS) or None) if kind == "bug" else None,
        created=now, updated=now,
    )
    db.session.add(item)
    db.session.flush()
    try:
        _save_images(item, images)
    except OSError:
        db.session.rollback()
        shutil.rmtree(os.path.join(feedback_dir(), str(item.id)), ignore_errors=True)
        logbuffer.logger("feedback").exception("Couldn't save feedback screenshots")
        return None, "The server couldn't save the screenshots"
    db.session.commit()
    return item, None

def add_event(item: Feedback, author: str, kind: str, body: str = "", user_id: Optional[int] = None,
              data: Optional[dict] = None) -> FeedbackEvent:
    event = FeedbackEvent(feedback_id=item.id, author=author, kind=kind, body=body, user_id=user_id,
                          data=json.dumps(data) if data is not None else None, created=db.getDatetimeISONow())
    db.session.add(event)
    item.updated = event.created
    return event

def set_status(item: Feedback, status: str, actor: User, note: str = "") -> Optional[str]:
    """A staff member moves the item. Returns a problem, or None once saved."""
    if status not in allowed_statuses(item):
        return f"Can't change from {item.status} to {status}"
    previous = item.status
    item.status = status
    if previous == "plan_ready" and status in ("approved", "changes_requested", "declined"):
        # The owner's answer to the agent's plan; the worker picks up changes_requested
        add_event(item, "staff", "plan_decision", note, actor.id, {"decision": status})
    add_event(item, "staff", "status", note, actor.id, {"from": previous, "to": status})
    db.session.commit()
    return None

def comment(item: Feedback, actor: User, text: str) -> tuple[Optional[FeedbackEvent], Optional[str]]:
    value, problem = _text({"comment": text}, "comment", required=True)
    if problem:
        return None, problem
    staff = is_staff_for(actor, item) and item.user_id != actor.id
    event = add_event(item, "staff" if staff else "user", "comment", value, actor.id)
    if not staff and item.status == "needs_info":
        # The sender answered: back to the owner's queue
        item.status = "new"
        add_event(item, "system", "status", "", None, {"from": "needs_info", "to": "new"})
    db.session.commit()
    return event, None

def delete(item: Feedback):
    for model in (FeedbackAttachment, FeedbackEvent):
        db.session.query(model).filter(model.feedback_id == item.id).delete()
    db.session.delete(item)
    db.session.commit()
    shutil.rmtree(os.path.join(feedback_dir(), str(item.id)), ignore_errors=True)

def delete_for_user(user_id: int):
    """When an account is deleted. Doesn't commit."""
    ids = list(db.session.scalars(select(Feedback.id).where(Feedback.user_id == user_id)))
    if not ids:
        return
    for model in (FeedbackAttachment, FeedbackEvent):
        db.session.query(model).filter(model.feedback_id.in_(ids)).delete()
    db.session.query(Feedback).filter(Feedback.id.in_(ids)).delete()
    for feedback_id in ids:
        shutil.rmtree(os.path.join(feedback_dir(), str(feedback_id)), ignore_errors=True)

def forget_manga(manga_id: int):
    """When a series is removed: items keep its title but lose the link. Doesn't commit."""
    db.session.query(Feedback).filter(Feedback.manga_id == manga_id).update({Feedback.manga_id: None})
