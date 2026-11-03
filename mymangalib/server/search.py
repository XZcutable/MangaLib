import re

from sqlalchemy import Select, select, func

from ..database import db
from ..models import Manga, UserMangaData, ContentTag, MangaContentTag

TERM_PATTERN = re.compile(r"(?<![:\",'])\b\w+\b(?![:\",'])")
TAG_PATTERN = re.compile(r"(?<!\w|!)tag:([\w,]+)")
NTAG_PATTERN = re.compile(r"!tag:([\w,]+)")
DQUOTE_PATTERN = re.compile(r"\"(.*?)\"")
QUOTE_PATTERN = re.compile(r"'(.*?)'")

UNREAD = "unread"
READ = "read"
TAGGED = "tagged"
UNTAGGED = "untagged"
IN_PROGRESS = "progress"
SFW = "sfw"
NSFW = "nsfw"

SPECIAL_TAGS = [READ, UNREAD, TAGGED, UNTAGGED, IN_PROGRESS, NSFW, SFW]

# TODO support partial search terms
def create_search_query(q: str) -> Select[tuple[int, str]]:
    q = q.lower()
    terms: list[str] = [*TERM_PATTERN.findall(q), *[*DQUOTE_PATTERN.findall(q), *QUOTE_PATTERN.findall(q)]]
    tags: list[str] = TAG_PATTERN.findall(q)
    ntags: list[str] = NTAG_PATTERN.findall(q)

    manga_query = select(Manga.id.label("id"), Manga.title).distinct()

    def is_special_tag(tag):
        return tag in SPECIAL_TAGS

    def handle_special_tag(tag, positive, metadata_query: Select[tuple[int]]):
        if tag == UNTAGGED:
            tag = TAGGED
            positive = not positive
        elif tag == SFW:
            tag = NSFW
            positive = not positive
        elif tag == UNREAD:
            tag = READ
            positive = not positive

        global user_id
        if tag == READ:
            user_id = db.session.getUserID()
            read_query = (
                select(Manga.id)
                .join(UserMangaData, (Manga.id == UserMangaData.manga_id) & (UserMangaData.user_id == user_id))
                .where(UserMangaData.is_read)
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(read_query))
            else:
                filter = filter.where(~Manga.id.in_(read_query))
            return filter
        elif tag == TAGGED:
            tag_query = (
                select(MangaContentTag.manga_id)
                .group_by(MangaContentTag.manga_id)
                .having(func.count() > 0)
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(tag_query))
            else:
                filter = filter.where(~Manga.id.in_(tag_query))
            return filter
        elif tag == IN_PROGRESS:
            user_id = db.session.getUserID()
            progress_query = (
                select(Manga.id)
                .join(UserMangaData, (Manga.id == UserMangaData.manga_id) & (UserMangaData.user_id == user_id))
                .where((~UserMangaData.is_read) & ((UserMangaData.current_chapter > 1) | (UserMangaData.current_page > 1)))
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(progress_query))
            else:
                filter = filter.where(~Manga.id.in_(progress_query))
            return filter
        elif tag == NSFW:
            nsfw_query = (
                select(MangaContentTag.manga_id)
                .join(ContentTag, ContentTag.tag == MangaContentTag.tag)
                .where(ContentTag.nsfw)
            )
            filter = metadata_query
            if positive:
                filter = filter.where(Manga.id.in_(nsfw_query))
            else:
                filter = filter.where(~Manga.id.in_(nsfw_query))
            return filter
        else:
            pass

    def replace_symbols(ls: list[str]):
        for i in range(len(ls)):
            ls[i] = ls[i].replace("_", " ")
            ls[i] = ls[i].strip(", ")

    def split_tags(tags: list[str], some: list[str], all: list[list[str]]):
        for tag in tags:
            if ',' in tag:
                all.append(tag.split(','))
            else:
                some.append(tag)
    
    replace_symbols(terms)
    replace_symbols(tags)
    replace_symbols(ntags)

    for term in terms:
        manga_query = manga_query.where(Manga.title.contains(term))

    if len(tags) or len(ntags):
        manga_query = manga_query.outerjoin(MangaContentTag, Manga.id == MangaContentTag.manga_id)

    if len(tags) > 0:
        or_tags:list[str] = []
        and_tags_list:list[list[str]] = []
        split_tags(tags, or_tags, and_tags_list)

        for or_tag in [tag for tag in or_tags]:
            if is_special_tag(or_tag):
                manga_query = handle_special_tag(or_tag, True, manga_query)
                or_tags.remove(or_tag)

        if len(or_tags):
            manga_query = manga_query.where(MangaContentTag.tag.in_(or_tags))

        for and_tags in and_tags_list:
            for and_tag in [tag for tag in and_tags]:
                if is_special_tag(and_tag):
                    and_tags.remove(and_tag)
                    manga_query = handle_special_tag(and_tag, True, manga_query)
            if len(and_tags):
                tag_query = (
                    select(MangaContentTag.manga_id)
                    .where(MangaContentTag.tag.in_(and_tags))
                    .group_by(MangaContentTag.manga_id)
                    .having(func.count() == len(and_tags))
                )
                manga_query = manga_query.where(Manga.id.in_(tag_query))

    if len(ntags) > 0:
        nor_tags:list[str] = []
        nand_tags_list:list[list[str]] = []
        split_tags(ntags, nor_tags, nand_tags_list)

        for nor_tag in [tag for tag in nor_tags]:
            if is_special_tag(nor_tag):
                manga_query = handle_special_tag(nor_tag, False, manga_query)
                nor_tags.remove(nor_tag)

        for nand_tags in nand_tags_list:
            for nand_tag in [tag for tag in nand_tags]:
                if is_special_tag(nand_tag):
                    manga_query = handle_special_tag(nand_tag, False, manga_query)
                else:
                    nor_tags.append(nand_tag)

        if len(nor_tags):
            tag_query = (
                select(MangaContentTag.manga_id)
                .where(MangaContentTag.tag.in_(nor_tags))
                .group_by(MangaContentTag.manga_id)
                .having(func.count() > 0)
            )
            manga_query = manga_query.where(Manga.id.not_in(tag_query))

    return manga_query
