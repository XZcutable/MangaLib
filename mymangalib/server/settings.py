from mymangalib.helpers import validate_string
from typing import Final

PATHS: Final[set] = set()
SUPPORTED_IMAGE_TYPES: Final[tuple] = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif')
SUPPORTED_ARCHIVE_TYPES: Final[tuple] = ('.cbz', '.zip', '.pdf')

def has_path(path: str) -> bool:
    validate_string(path)
    return path in PATHS

def update_paths():
    PATHS.clear()
    #[path[0] for path in Path.query.values(Path.path)]