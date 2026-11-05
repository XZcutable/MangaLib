"""The server's version. Server and app share one version number (pyproject.toml and
manga-site/package.json), which the release script bumps together."""
import re
from importlib import metadata
from pathlib import Path


def _from_pyproject():
    try:
        text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def _detect():
    # A checkout run with `flask run` may have an older install in site-packages, so prefer
    # the pyproject.toml next to this code when there is one
    found = _from_pyproject()
    if found:
        return found
    try:
        return metadata.version("mymangalib")
    except metadata.PackageNotFoundError:
        return "0.0.0"


__version__ = _detect()


def parse(version):
    """'v1.2.3' -> (1, 2, 3). Missing or non-numeric parts count as 0."""
    parts = str(version or "").strip().lstrip("vV").split("-")[0].split(".")
    numbers = []
    for part in parts[:3]:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def is_newer(candidate, current=None):
    return parse(candidate) > parse(current or __version__)
