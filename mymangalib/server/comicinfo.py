"""Reads and writes ComicInfo.xml, the metadata file most comic and manga tools put inside .cbz files.
Only file work happens here; server/metadata.py decides what goes into the database."""
import os, time, zipfile
import xml.etree.ElementTree as ET
from typing import Optional

FILE_NAME = "ComicInfo.xml"
MAX_SIZE = 1024 * 1024  # A real ComicInfo.xml is a few KB; anything bigger isn't parsed

# Field name used by the API -> ComicInfo element
ELEMENTS = {
    "title": "Series",
    "summary": "Summary",
    "year": "Year",
    "writer": "Writer",
    "artist": "Penciller",
    "publisher": "Publisher",
    "genres": "Genre",
    "web": "Web",
    "language": "LanguageISO",
    "format": "Format",
    "reading_direction": "Manga",
    "age_rating": "AgeRating",
}

# The schema's element order. Some tools validate it, so new elements go in their proper place.
SCHEMA_ORDER = [
    "Title", "Series", "Number", "Count", "Volume", "AlternateSeries", "AlternateNumber", "AlternateCount",
    "Summary", "Notes", "Year", "Month", "Day", "Writer", "Penciller", "Inker", "Colorist", "Letterer",
    "CoverArtist", "Editor", "Translator", "Publisher", "Imprint", "Genre", "Tags", "Web", "PageCount",
    "LanguageISO", "Format", "BlackAndWhite", "Manga", "Characters", "Teams", "Locations", "ScanInformation",
    "StoryArc", "StoryArcNumber", "SeriesGroup", "AgeRating", "Pages", "CommunityRating",
    "MainCharacterOrTeam", "Review", "GTIN",
]

class ComicInfoError(Exception):
    pass

def parse(data: bytes) -> dict:
    """Fields found in a ComicInfo.xml. Missing or empty elements are left out."""
    if len(data) > MAX_SIZE:
        return {}
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return {}

    fields = {}
    for field, element in ELEMENTS.items():
        node = root.find(element)
        text = (node.text or "").strip() if node is not None else ""
        if not text:
            continue
        if field == "year":
            if text.isdigit() and 1000 <= int(text) <= 9999:
                fields["year"] = int(text)
        elif field == "reading_direction":
            # Only right-to-left says anything about direction; "Yes" just means it's manga
            if text == "YesAndRightToLeft":
                fields["reading_direction"] = "rtl"
        elif field == "genres":
            genres = [genre.strip() for genre in text.split(",") if genre.strip()]
            if genres:
                fields["genres"] = genres
        else:
            fields[field] = text
    return fields

def _element_text(field: str, value) -> Optional[str]:
    if value is None or value == "" or value == []:
        return None
    if field == "genres":
        return ", ".join(value)
    if field == "reading_direction":
        return "YesAndRightToLeft" if value == "rtl" else "No"
    return str(value)

def build(existing: Optional[bytes], fields: dict) -> bytes:
    """A ComicInfo.xml with `fields` set (None removes one). Everything else in `existing` is kept,
    including per-volume details like Number, Volume and Pages."""
    root = None
    if existing and len(existing) <= MAX_SIZE:
        try:
            root = ET.fromstring(existing)
        except ET.ParseError:
            root = None
    if root is None or root.tag != "ComicInfo":
        root = ET.Element("ComicInfo")

    for field, value in fields.items():
        element = ELEMENTS.get(field)
        if element is None:
            continue
        text = _element_text(field, value)
        node = root.find(element)
        if text is None:
            if node is not None:
                root.remove(node)
        else:
            if node is None:
                node = ET.SubElement(root, element)
            node.text = text

    # Put the elements in schema order; unknown ones keep their relative order at the end
    position = {name: index for index, name in enumerate(SCHEMA_ORDER)}
    children = list(root)
    children.sort(key=lambda child: position.get(child.tag, len(SCHEMA_ORDER)))
    for child in list(root):
        root.remove(child)
    root.extend(children)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

def _entry_name(archive: zipfile.ZipFile) -> Optional[str]:
    """The ComicInfo.xml entry, preferring one at the top of the archive."""
    matches = [name for name in archive.namelist() if os.path.basename(name).lower() == FILE_NAME.lower()]
    matches.sort(key=lambda name: name.count("/"))
    return matches[0] if matches else None

def read_archive(path: str) -> dict:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            name = _entry_name(archive)
            if name is None or archive.getinfo(name).file_size > MAX_SIZE:
                return {}
            return parse(archive.read(name))
    except (OSError, zipfile.BadZipFile, KeyError):
        return {}

def read_folder(path: str) -> dict:
    file_path = os.path.join(path, FILE_NAME)
    try:
        if os.path.getsize(file_path) > MAX_SIZE:
            return {}
        with open(file_path, "rb") as file:
            return parse(file.read())
    except OSError:
        return {}

def _replace(source: str, target: str):
    """os.replace, retried briefly because Windows refuses while a reader has the file open."""
    for attempt in range(10):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.5)

def write_archive(path: str, fields: dict):
    """Rewrites a .cbz/.zip with an updated ComicInfo.xml. The new archive is checked before it replaces
    the old one, so a failure leaves the original untouched."""
    partial = path + ".partial"
    try:
        with zipfile.ZipFile(path, "r") as source:
            name = _entry_name(source)
            existing = source.read(name) if name and source.getinfo(name).file_size <= MAX_SIZE else None
            entries = [info for info in source.infolist() if info.filename != name]
            with zipfile.ZipFile(partial, "w") as target:
                # ComicInfo.xml goes first so tools that only read the start find it quickly
                target.writestr(FILE_NAME, build(existing, fields), compress_type=zipfile.ZIP_DEFLATED)
                for info in entries:
                    if info.is_dir():
                        target.writestr(info, b"")
                    else:
                        with source.open(info) as data, target.open(info, "w") as out:
                            while chunk := data.read(1024 * 1024):
                                out.write(chunk)

        with zipfile.ZipFile(partial, "r") as check:
            if check.testzip() is not None or len(check.infolist()) != len(entries) + 1:
                raise ComicInfoError(f"The rewritten copy of {os.path.basename(path)} didn't check out")
        _replace(partial, path)
    except (OSError, zipfile.BadZipFile) as error:
        raise ComicInfoError(f"Couldn't update {os.path.basename(path)}: {error}") from error
    finally:
        if os.path.exists(partial):
            os.remove(partial)

def write_folder(path: str, fields: dict):
    """Creates or updates ComicInfo.xml in a folder."""
    file_path = os.path.join(path, FILE_NAME)
    existing = None
    try:
        with open(file_path, "rb") as file:
            existing = file.read()
    except OSError:
        pass
    partial = file_path + ".partial"
    try:
        with open(partial, "wb") as file:
            file.write(build(existing, fields))
        _replace(partial, file_path)
    except OSError as error:
        raise ComicInfoError(f"Couldn't write {file_path}: {error}") from error
    finally:
        if os.path.exists(partial):
            os.remove(partial)
