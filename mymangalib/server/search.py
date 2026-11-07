"""The search language shared by the new app and the classic pages.

    one piece "a phrase"     title contains each word / the phrase (any case)
    tag:fantasy|action       has either tag            tag:fantasy&action   has both
    tag:"slice of life"      values with spaces are quoted
    nsfw:gore  nsfw:         NSFW tags (empty = any NSFW tag)
    language:english|japanese
    is:unread  is:progress   the user's own reading state
    -tag:romance  -nsfw  -word   a leading "-" means not

`&` binds tighter than `|`. Only double quotes group words; a single quote is an ordinary character.
Future keys (rating:, author:, year:...) are new KEYS entries; comparison characters like > < .. stay
part of a value, so `year:2015..2020` already parses as one value.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from sqlalchemy import Select, and_, false, func, not_, or_, select

from ..database import db
from ..models import ContentTag, Manga, MangaContentTag, MangaMetadata, UserMangaData
from . import languages

@dataclass
class Filter:
    key: str
    negated: bool = False
    # Or-list of and-lists: tag:a|b&c -> [["a"], ["b", "c"]]
    groups: list[list[str]] = field(default_factory=list)

@dataclass
class Query:
    terms: list[tuple[str, bool]] = field(default_factory=list)  # (text, negated)
    filters: list[Filter] = field(default_factory=list)

# --- Parsing ---

def _split(text: str, separators: str) -> list[str]:
    """Splits on any of `separators` outside double quotes. Quotes are kept."""
    parts, current, quoted = [], "", False
    for char in text:
        if char == '"':
            quoted = not quoted
            current += char
        elif not quoted and char in separators:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return parts

def _unquote(text: str) -> str:
    return text.replace('"', "").strip()

def _value_groups(value: str) -> list[list[str]]:
    groups = []
    for part in _split(value, "|"):
        items = [_unquote(item).lower() for item in _split(part, "&")]
        items = list(dict.fromkeys(item for item in items if item))
        if items:
            groups.append(items)
    return groups

def parse(q: str) -> Query:
    query = Query()
    for token in _split(q or "", " \t\n"):
        if not token or token == "-":
            continue
        negated = token.startswith("-")
        body = token[1:] if negated else token

        colon, quote = body.find(":"), body.find('"')
        key = body[:colon].lower() if colon > 0 and (quote == -1 or colon < quote) else None
        if key in KEYS:
            query.filters.append(Filter(key, negated, _value_groups(body[colon + 1:])))
        elif negated and body.lower() == "nsfw":
            query.filters.append(Filter("nsfw", True, []))
        else:
            text = _unquote(body)
            if text:
                query.terms.append((text, negated))
    return query

# --- Conditions ---

def _tags_condition(groups: list[list[str]], nsfw_only: bool):
    def with_tags(tags: list[str]):
        tag_query = select(MangaContentTag.manga_id).where(MangaContentTag.tag.in_(tags))
        if nsfw_only:
            tag_query = tag_query.join(ContentTag, ContentTag.tag == MangaContentTag.tag).where(ContentTag.nsfw)
        tag_query = tag_query.group_by(MangaContentTag.manga_id).having(func.count() == len(tags))
        return Manga.id.in_(tag_query)
    return or_(*(with_tags(tags) for tags in groups))

def _any_nsfw():
    return Manga.id.in_(
        select(MangaContentTag.manga_id)
        .join(ContentTag, ContentTag.tag == MangaContentTag.tag)
        .where(ContentTag.nsfw)
    )

def tag_condition(groups):
    return _tags_condition(groups, nsfw_only=False) if groups else None

def nsfw_condition(groups):
    return _tags_condition(groups, nsfw_only=True) if groups else _any_nsfw()

def language_condition(groups):
    # Only "or" makes sense for a single-valued field, so & is read as |
    words = [word for group in groups for word in group]
    if not words:
        return None
    codes = [code for code in (languages.search_code(word) for word in words) if code]
    if not codes:
        return false()
    return Manga.id.in_(select(MangaMetadata.manga_id).where(MangaMetadata.language.in_(codes)))

def _user_manga(*conditions):
    return Manga.id.in_(
        select(UserMangaData.manga_id)
        .where(UserMangaData.user_id == db.session.getUserID(), *conditions)
    )

def _status(word: str):
    if word == "read":
        return _user_manga(UserMangaData.is_read)
    if word == "unread":
        return not_(_user_manga(UserMangaData.is_read))
    if word == "progress":
        return _user_manga(
            ~UserMangaData.is_read,
            (UserMangaData.current_chapter > 1) | (UserMangaData.current_page > 1),
        )
    tagged = Manga.id.in_(select(MangaContentTag.manga_id))
    if word == "tagged":
        return tagged
    if word == "untagged":
        return not_(tagged)
    return false()

STATUSES = ["read", "unread", "progress", "tagged", "untagged"]

def status_condition(groups):
    if not groups:
        return None
    return or_(*(and_(*(_status(word) for word in group)) for group in groups))

@dataclass
class KeySpec:
    build: Callable[[list[list[str]]], Optional[object]]
    ops: str = "|&"

KEYS: dict[str, KeySpec] = {
    "tag": KeySpec(tag_condition),
    "nsfw": KeySpec(nsfw_condition),
    "language": KeySpec(language_condition, ops="|"),
    "is": KeySpec(status_condition),
}

def create_search_query(q: str) -> Select[tuple[int, str]]:
    parsed = parse(q)
    manga_query = select(Manga.id.label("id"), Manga.title)

    for text, negated in parsed.terms:
        # casefold() is registered on every SQLite connection (database.py); LIKE alone ignores
        # case only for A-Z
        condition = func.casefold(Manga.title).contains(text.casefold(), autoescape=True)
        manga_query = manga_query.where(not_(condition) if negated else condition)

    for search_filter in parsed.filters:
        condition = KEYS[search_filter.key].build(search_filter.groups)
        if condition is not None:
            manga_query = manga_query.where(not_(condition) if search_filter.negated else condition)

    return manga_query
