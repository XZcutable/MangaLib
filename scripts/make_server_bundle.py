"""Packs the server update bundle that running servers download from GitHub Releases
(see mymangalib/server/updater.py):

    python scripts/make_server_bundle.py <version> <built front end folder> <output .tar.gz>

The bundle holds the mymangalib package, the built front end, pyproject.toml, requirements.txt and
manifest.json. requirements.txt is made from pyproject.toml's dependencies: installed servers read it to
install anything new before they switch to the bundle. Called by scripts/release.mjs.
"""
import io, json, os, re, sys, tarfile, time, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mymangalib.update_files import PROTOCOL  # noqa: E402

SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def add_tree(archive: tarfile.TarFile, source: Path, prefix: str):
    for folder, dirs, files in os.walk(source):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        for name in sorted(files):
            path = Path(folder, name)
            if path.suffix in SKIP_SUFFIXES:
                continue
            archive.add(path, arcname=f"{prefix}/{path.relative_to(source).as_posix()}", recursive=False,
                        filter=clean)


def add_bytes(archive: tarfile.TarFile, name: str, data: bytes):
    info = tarfile.TarInfo(name)
    info.size, info.mtime = len(data), int(time.time())
    archive.addfile(clean(info), io.BytesIO(data))


def clean(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o755 if info.isdir() else 0o644
    return info


def requirements(pyproject: str) -> str:
    return "".join(f"{dependency}\n" for dependency in tomllib.loads(pyproject)["project"]["dependencies"])


def main(version: str, frontend: str, output: str):
    frontend_dir = Path(frontend)
    if not (frontend_dir / "index.html").is_file():
        sys.exit(f"No built front end at {frontend_dir}")
    manifest = {
        "version": version,
        "protocol": PROTOCOL,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        add_bytes(archive, "manifest.json", json.dumps(manifest, indent=2).encode())
        # The server reads its version from this pyproject.toml, so it must match the bundle's
        pyproject = re.sub(r'^version\s*=\s*"[^"]*"', f'version = "{version}"',
                           (ROOT / "pyproject.toml").read_text(encoding="utf-8"), count=1, flags=re.MULTILINE)
        add_bytes(archive, "pyproject.toml", pyproject.encode())
        add_bytes(archive, "requirements.txt", requirements(pyproject).encode())
        add_tree(archive, ROOT / "mymangalib", "mymangalib")
        add_tree(archive, frontend_dir, "frontend")
    print(f"Wrote {output} ({os.path.getsize(output) / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
