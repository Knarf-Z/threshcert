"""Hash every file whose content is reproducible.

``results/run_metadata.v2.json`` is deliberately excluded: it carries PIDs,
timings and platform strings, which differ between runs by design. The
canonical result is included, and it must be byte-identical on every replay.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
IGNORED_PARTS = {".venv", "__pycache__", ".git"}
NON_DETERMINISTIC = {
    "results/run_metadata.v2.json",
    "results/replay_canonical.json",
    "results/replay_metadata.json",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    lines: list[str] = []
    skipped: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == MANIFEST:
            continue
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        posix = relative.as_posix()
        if posix in NON_DETERMINISTIC:
            skipped.append(posix)
            continue
        lines.append(f"{digest(path)}  {posix}")
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"MANIFEST={MANIFEST}")
    print(f"FILES={len(lines)}")
    for name in skipped:
        print(f"EXCLUDED_NON_DETERMINISTIC={name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
