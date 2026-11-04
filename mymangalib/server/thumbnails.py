"""Small cover images for list views. Full-size covers from digital volumes can be several MB each,
which is too much for a phone loading a grid of them. Thumbnails are made once and cached on disk."""
import os, zipfile
from typing import Optional

import pymupdf

from ..models import Manga, Page

THUMBNAIL_WIDTH = 360
JPEG_QUALITY = 80

def read_page_bytes(page: Page) -> Optional[bytes]:
    chapter = page.chapter
    try:
        if chapter.archive_type in (".zip", ".cbz"):
            with zipfile.ZipFile(chapter.path, "r") as archive:
                return archive.read(page.file_name)
        elif chapter.archive_type == ".pdf":
            with pymupdf.open(chapter.path) as pdf:
                image = pdf.extract_image(int(page.file_name))
            return image["image"] if image else None
        elif chapter.archive_type is None:
            with open(os.path.join(chapter.path, page.file_name), "rb") as image_file:
                return image_file.read()
    except (OSError, KeyError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"Unable to read page {page.number} of '{chapter.path}': {error}")
    return None

def make_thumbnail(image_data: bytes) -> Optional[bytes]:
    try:
        pixmap = pymupdf.Pixmap(image_data)
        if pixmap.width > THUMBNAIL_WIDTH:
            height = max(1, round(pixmap.height * THUMBNAIL_WIDTH / pixmap.width))
            pixmap = pymupdf.Pixmap(pixmap, THUMBNAIL_WIDTH, height, None)
        if pixmap.alpha or pixmap.n not in (1, 3):
            # JPEG has no transparency and needs gray or RGB
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
            if pixmap.alpha:
                pixmap = pymupdf.Pixmap(pixmap, 0)
        return pixmap.tobytes("jpg", jpg_quality=JPEG_QUALITY)
    except Exception as error:
        # MuPDF can't decode some formats (e.g. WebP) and raises its own error types.
        # The cover route then serves the original image instead.
        print(f"Unable to make thumbnail: {error}")
        return None

def cover_thumbnail_path(manga: Manga, cover_page: Page, cache_dir: str) -> Optional[str]:
    """Path to a cached JPEG thumbnail of the cover, made if missing or older than the source."""
    source = cover_page.chapter.path if cover_page.chapter.archive_type else os.path.join(cover_page.chapter.path, cover_page.file_name)
    try:
        source_modified = os.path.getmtime(source)
    except OSError:
        return None

    thumbnail_path = os.path.join(cache_dir, f"{manga.id}.jpg")
    if os.path.isfile(thumbnail_path) and os.path.getmtime(thumbnail_path) >= source_modified:
        return thumbnail_path

    image_data = read_page_bytes(cover_page)
    thumbnail = make_thumbnail(image_data) if image_data else None
    if thumbnail is None:
        return None

    os.makedirs(cache_dir, exist_ok=True)
    temp_path = f"{thumbnail_path}.{os.getpid()}.tmp"
    with open(temp_path, "wb") as thumbnail_file:
        thumbnail_file.write(thumbnail)
    os.replace(temp_path, thumbnail_path) # Readers never see a half-written file
    return thumbnail_path
