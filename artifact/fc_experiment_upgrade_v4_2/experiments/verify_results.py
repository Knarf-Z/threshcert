from __future__ import annotations

import json

from common import RESULTS, sha256
from make_manifest import source_inventory


def main() -> None:
    manifest_path = RESULTS / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected_results = {
        item["name"]: item for item in manifest.get("files", [])
    }
    actual_results = {
        path.name
        for path in RESULTS.iterdir()
        if path.is_file() and path.name != manifest_path.name
    }
    missing = sorted(set(expected_results) - actual_results)
    unlisted = sorted(actual_results - set(expected_results))
    mismatched = []
    for name, expected in expected_results.items():
        path = RESULTS / name
        if not path.is_file():
            continue
        if (
            path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            mismatched.append(name)

    sources, source_tree_sha256 = source_inventory()
    expected_sources = {
        item["name"]: (item["bytes"], item["sha256"])
        for item in manifest.get("source_files", [])
    }
    actual_sources = {
        item["name"]: (item["bytes"], item["sha256"])
        for item in sources
    }
    source_mismatch = (
        expected_sources != actual_sources
        or manifest.get("source_tree_sha256") != source_tree_sha256
    )

    if missing or unlisted or mismatched or source_mismatch:
        raise SystemExit(
            "manifest verification failed: "
            f"missing={missing}, unlisted={unlisted}, "
            f"mismatched={mismatched}, source_mismatch={source_mismatch}"
        )
    print(
        "Manifest verification passed: "
        f"{len(expected_results)} result files and "
        f"{len(expected_sources)} source files."
    )


if __name__ == "__main__":
    main()
