#!/usr/bin/env python3
"""Migrate Focus Workspace data from standalone workstation to Lumbergh."""

import argparse
import json
import shutil
from pathlib import Path


FOCUS_FILES = ["tasks.json", "archive.json", "notes.json"]
TARGET_DIR = Path.home() / ".config" / "lumbergh" / "focus"


def has_data(path: Path) -> bool:
    """Return True if the file exists and contains non-empty TinyDB data."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        default_table = data.get("_default", {})
        return bool(default_table)
    except (json.JSONDecodeError, Exception):
        return False


def migrate_file(name: str, source_dir: Path) -> str:
    """Copy one data file from source_dir to TARGET_DIR.

    Returns a status string describing what happened.
    """
    src = source_dir / name
    dst = TARGET_DIR / name

    if not src.exists():
        print(f"  {name}: SKIP — source file not found ({src})")
        return "source not found"

    if has_data(dst):
        print(f"  {name}: SKIP — target already has data ({dst})")
        return "skipped (target exists)"

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  {name}: OK — copied {src} → {dst}")
    return "migrated"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate Focus Workspace data to ~/.config/lumbergh/focus/"
    )
    parser.add_argument(
        "--source-dir",
        default=str(Path.home() / "src" / "work" / "workstation"),
        help="Path to standalone workstation directory (default: ~/src/work/workstation)",
    )
    args = parser.parse_args()

    source_dir = Path(args.source_dir).expanduser().resolve()
    print(f"Source : {source_dir}")
    print(f"Target : {TARGET_DIR}")
    print()

    if not source_dir.exists():
        print(f"ERROR: source directory does not exist: {source_dir}")
        raise SystemExit(1)

    results = {}
    for name in FOCUS_FILES:
        results[name] = migrate_file(name, source_dir)

    print()
    print("Done.")
    for name, status in results.items():
        print(f"  {name}: {status}")


if __name__ == "__main__":
    main()
