#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
EXCLUDED_PARTS = {
    ".runtime",
    "__pycache__",
    "cache",
    "node_modules",
}


def manifest_text() -> str:
    lines: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == MANIFEST:
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() == ".log":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative.as_posix()}")
    return "\n".join(lines) + "\n"


parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
expected = manifest_text()

if args.check:
    if not MANIFEST.exists() or MANIFEST.read_text(encoding="utf-8") != expected:
        raise SystemExit("MANIFEST=FAIL")
    print("MANIFEST=PASS")
else:
    MANIFEST.write_text(expected, encoding="utf-8")
    print(f"MANIFEST=WRITTEN files={len(expected.splitlines())}")
