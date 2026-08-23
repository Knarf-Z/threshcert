from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone

from common import RESULTS, ROOT, ensure_results, sha256, write_json


def source_paths():
    patterns = (
        "*.ps1",
        "*.md",
        "VERSION",
        "requirements.txt",
        "config/*.json",
        "experiments/*.py",
        "tests/*.py",
        "contracts/*.toml",
        "contracts/src/*.sol",
        "contracts/test/*.sol",
    )
    paths = {
        path
        for pattern in patterns
        for path in ROOT.glob(pattern)
        if path.is_file()
    }
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def source_inventory():
    inventory = []
    tree_digest = hashlib.sha256()
    for path in source_paths():
        relative = path.relative_to(ROOT).as_posix()
        digest = sha256(path)
        inventory.append({
            "name": relative,
            "bytes": path.stat().st_size,
            "sha256": digest,
        })
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(digest.encode("ascii"))
        tree_digest.update(b"\n")
    return inventory, tree_digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--foundry-status", default="unknown")
    parser.add_argument("--python-status", default="unknown")
    args = parser.parse_args()
    ensure_results()
    files = []
    for path in sorted(RESULTS.glob("*")):
        if path.is_file() and path.name != "run_manifest.json":
            files.append({
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    sources, source_tree_sha256 = source_inventory()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    write_json(
        RESULTS / "run_manifest.json",
        {
            "package_version": version,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "python_status": args.python_status,
            "foundry_status": args.foundry_status,
            "files": files,
            "source_files": sources,
            "source_tree_sha256": source_tree_sha256,
        },
    )


if __name__ == "__main__":
    main()
