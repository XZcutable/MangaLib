"""Where server updates live on disk, shared by the supervisor (which picks the code to run) and the
updater (which downloads and applies updates). Neither imports Flask here, so the supervisor stays small.

<update dir>/              In Docker: /var/db/updates, next to the database
    state.json             The updater's status, shown in Settings
    downloads/             Downloads in progress (<name>.part) and finished bundles
    versions/<version>/    Unpacked updates: mymangalib/, frontend/, deps/, manifest.json
    current                The applied version, or missing for the code the server was installed with
    apply.json             Written when an update is applied; removed once the new version has started
    last-start.json        The supervisor's note when an update didn't start and was rolled back
    backups/               Database copies made before each update (the last few)
"""
import json, os, shutil

# Exit code the server uses to ask the supervisor to restart it (to apply an update)
RESTART_EXIT_CODE = 75
# Bumped when the bundle layout or the supervisor <-> server handshake changes. A bundle that needs a
# newer supervisor than the one in the image can't be applied from Settings; pull a new image instead.
PROTOCOL = 1


class Layout:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.versions = os.path.join(self.root, "versions")
        self.downloads = os.path.join(self.root, "downloads")
        self.backups = os.path.join(self.root, "backups")
        self.state_file = os.path.join(self.root, "state.json")
        self.current_file = os.path.join(self.root, "current")
        self.apply_file = os.path.join(self.root, "apply.json")
        self.last_start_file = os.path.join(self.root, "last-start.json")

    def version_dir(self, version: str) -> str:
        return os.path.join(self.versions, version)

    def has_version(self, version: str | None) -> bool:
        return bool(version) and os.path.isfile(os.path.join(self.version_dir(version), "mymangalib", "__init__.py"))

    def read_current(self) -> str | None:
        try:
            with open(self.current_file, encoding="utf-8") as file:
                return file.read().strip() or None
        except OSError:
            return None

    def write_current(self, version: str | None):
        if not version:
            remove(self.current_file)
            return
        write_text(self.current_file, version)

    def read_json(self, path: str) -> dict | None:
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def write_json(self, path: str, data: dict):
        write_text(path, json.dumps(data, indent=2))


def write_text(path: str, text: str):
    """Writes through a temporary file, so a crash never leaves half a file behind."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        file.write(text)
    os.replace(temporary, path)


def remove(path: str):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except FileNotFoundError:
        pass
