#!/usr/bin/env python3
"""Build a deterministic author-free v16 review ZIP."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "artifact" / "anonymous_v16" / "anonymous_v16_artifact.zip"
FIXED_TIME = (2026, 8, 23, 0, 0, 0)
INCLUDE_DIRECTORIES = (
    "artifact/anonymous_v16",
    "artifact/finite_toy_delivery_extension",
    "artifact/joint_incidence_refinement",
    "artifact/ope_process_positive",
    "artifact/process_route_stress_fixture",
    "artifact/reviewer_revision_v77",
)
EXCLUDED_PARTS = {
    "anonymous_v16_artifact.zip",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".runtime",
    "artifacts",
    "cache",
}
TEXT_SUFFIXES = {".md", ".txt", ".py", ".js", ".mjs", ".ts", ".sol", ".json", ".yml", ".yaml"}
FORBIDDEN_IDENTITY_MARKERS = (
    b"Jiaqi",
    b"Honghao",
    b"Knarf-Z",
    b"0009-0005-3271-3106",
    b"0000-0002-1934-3391",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_files() -> list[Path]:
    files: set[Path] = set()
    for relative in INCLUDE_DIRECTORIES:
        directory = ROOT / relative
        if not directory.is_dir():
            raise FileNotFoundError(f"required artifact directory missing: {relative}")
        for path in directory.rglob("*"):
            if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
                files.add(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def build(output: Path) -> tuple[int, int, str]:
    members: dict[str, bytes] = {}
    for path in selected_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative == "artifact/anonymous_v16/reproduce.py":
            name = "reproduce.py"
        elif relative == "artifact/anonymous_v16/README.md":
            name = "README.md"
        else:
            name = relative
        data = path.read_bytes()
        if path.suffix.lower() in TEXT_SUFFIXES:
            for marker in FORBIDDEN_IDENTITY_MARKERS:
                if marker.lower() in data.lower():
                    raise ValueError(f"identity marker found in anonymous member: {relative}")
        members[name] = data
    manifest = "".join(f"{sha256(data)}  {name}\n" for name, data in sorted(members.items())).encode("ascii")
    members["MANIFEST.sha256"] = manifest
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in sorted(members.items()):
            archive.writestr(zip_info(name), data)
    payload = output.read_bytes()
    return len(members), len(payload), sha256(payload)


def verify(output: Path) -> tuple[int, int, str]:
    with zipfile.ZipFile(output, "r") as archive:
        names = archive.namelist()
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("archive entries are not unique and sorted")
        expected = {}
        for line in archive.read("MANIFEST.sha256").decode("ascii").splitlines():
            digest, name = line.split("  ", 1)
            expected[name] = digest
        payload_names = [name for name in names if name != "MANIFEST.sha256"]
        if sorted(expected) != payload_names:
            raise ValueError("anonymous manifest member set mismatch")
        for name in payload_names:
            data = archive.read(name)
            if sha256(data) != expected[name]:
                raise ValueError(f"anonymous member digest mismatch: {name}")
            if Path(name).suffix.lower() in TEXT_SUFFIXES:
                for marker in FORBIDDEN_IDENTITY_MARKERS:
                    if marker.lower() in data.lower():
                        raise ValueError(f"identity marker escaped into archive: {name}")
    payload = output.read_bytes()
    return len(names), len(payload), sha256(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    entries, size, digest = verify(output) if args.verify_only else build(output)
    if not args.verify_only:
        entries, size, digest = verify(output)
    print("ANONYMOUS_ARTIFACT=PASS")
    print(f"ANONYMOUS_ARTIFACT_ENTRIES={entries}")
    print(f"ANONYMOUS_ARTIFACT_BYTES={size}")
    print(f"ANONYMOUS_ARTIFACT_SHA256={digest}")


if __name__ == "__main__":
    main()
