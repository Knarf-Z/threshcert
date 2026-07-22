#!/usr/bin/env python3
"""Verify every distributable file against MANIFEST.sha256."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
IGNORED_PARTS = {
    ".git",
    "__pycache__",
    ".idea",
    ".venv",
    "venv",
    "node_modules",
    "artifacts",
    "cache",
    ".claude",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def distributable_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if path == MANIFEST or any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.is_file():
            files[relative.as_posix()] = path
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="regenerate the sorted manifest before verifying it",
    )
    args = parser.parse_args()

    files = distributable_files()
    if args.write:
        lines = [f"{digest(files[relative])}  ./{relative}" for relative in sorted(files)]
        MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")

    entries: dict[str, str] = {}
    for number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        if match is None:
            raise SystemExit(f"invalid manifest line {number}: {line!r}")
        expected, relative = match.groups()
        if relative in entries:
            raise SystemExit(f"duplicate manifest entry: {relative}")
        entries[relative] = expected

    missing = sorted(set(entries) - set(files))
    unlisted = sorted(set(files) - set(entries))
    mismatched = sorted(
        relative
        for relative in set(entries) & set(files)
        if digest(files[relative]) != entries[relative]
    )
    if missing or unlisted or mismatched:
        raise SystemExit(
            "manifest verification failed: "
            f"missing={missing}, unlisted={unlisted}, mismatched={mismatched}"
        )
    print(f"manifest_entries={len(entries)}")
    print("manifest_verification=PASS")


if __name__ == "__main__":
    main()
