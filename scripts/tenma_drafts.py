"""Make draft drawings of Tenma's poses with the OpenAI image API.

Drafts go to Tenma/drafts/<pose>/ (gitignored) and never reach the app by themselves: copy the one
you approve to Tenma/<pose>.png, then run `pnpm tenma:assets` in manga-site.

Needs (a ChatGPT subscription alone doesn't give API access):
  - An OpenAI API key with billing set up (platform.openai.com), in OPENAI_API_KEY or in
    ~/.mymangalib/openai-key (outside the repo, like the other secrets).
  - The openai package, which the server doesn't need: .venv/Scripts/python -m pip install openai

Usage (repo root):
  .venv/Scripts/python scripts/tenma_drafts.py                 # every pose not in Tenma/source yet
  .venv/Scripts/python scripts/tenma_drafts.py sad icon -n 3   # these poses, 3 drafts each
  .venv/Scripts/python scripts/tenma_drafts.py --list          # poses and whether they're done
"""

import argparse
import base64
import os
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TENMA = ROOT / "Tenma"
REFERENCE = TENMA / "Tenma.png"
SOURCE = TENMA / "source"
DRAFTS = TENMA / "drafts"
KEY_FILE = Path.home() / ".mymangalib" / "openai-key"


def load_poses() -> tuple[str, dict]:
    with open(TENMA / "poses.toml", "rb") as f:
        data = tomllib.load(f)
    return data["style"].strip(), data["poses"]


def is_done(name: str, pose: dict) -> bool:
    return pose.get("done", False) or any((d / f"{name}.png").exists() for d in (TENMA, SOURCE))


def api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        sys.exit(f"No API key: set OPENAI_API_KEY or put the key in {KEY_FILE}")
    return key


def main() -> None:
    style, poses = load_poses()
    parser = argparse.ArgumentParser(description="Draft Tenma poses with the OpenAI image API.")
    parser.add_argument("poses", nargs="*", help="pose names from Tenma/poses.toml (default: all not done)")
    parser.add_argument("-n", type=int, default=2, help="drafts per pose (default 2)")
    parser.add_argument("--model", default="gpt-image-1", help="OpenAI image model (default gpt-image-1)")
    parser.add_argument("--quality", default="high", choices=["low", "medium", "high"])
    parser.add_argument("--list", action="store_true", help="list the poses and stop")
    args = parser.parse_args()

    if args.list:
        for name, pose in poses.items():
            print(f"{'done' if is_done(name, pose) else 'todo':4}  {name:11} {pose.get('used_for', '')}")
        return

    unknown = [name for name in args.poses if name not in poses]
    if unknown:
        sys.exit(f"Unknown pose(s): {', '.join(unknown)}. See --list.")
    names = args.poses or [name for name, pose in poses.items() if not is_done(name, pose)]
    names = [name for name in names if name != "main"]
    if not names:
        print("Every pose is done.")
        return

    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("The openai package is missing: .venv/Scripts/python -m pip install openai")
    client = OpenAI(api_key=api_key())

    for name in names:
        pose = poses[name]
        out_dir = DRAFTS / name
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"{name}: asking for {args.n} draft(s)...", flush=True)
        with open(REFERENCE, "rb") as reference:
            result = client.images.edit(
                model=args.model,
                image=[reference],
                prompt=f"{style}\n\n{pose['prompt'].strip()}",
                size=pose.get("size", "1024x1536"),
                background="transparent",
                quality=args.quality,
                n=args.n,
            )
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for index, image in enumerate(result.data, start=1):
            path = out_dir / f"{stamp}-{index}.png"
            path.write_bytes(base64.b64decode(image.b64_json))
            print(f"  {path.relative_to(ROOT)}")

    print(f"\nPick the ones you like and copy them to {TENMA.relative_to(ROOT)}/<pose>.png,")
    print("then run `pnpm tenma:assets` in manga-site.")


if __name__ == "__main__":
    main()
