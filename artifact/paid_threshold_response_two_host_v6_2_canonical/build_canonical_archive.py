from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


MODULES = (
    "paid_threshold_response_two_host_v6",
    "rsp_soundness_supplement_v2",
    "external_threshold_service_audit_v1",
)
ZIP_TIMESTAMP = (2026, 8, 9, 0, 0, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> int:
    module_root = Path(__file__).resolve().parent
    artifact_root = module_root.parent
    parser = argparse.ArgumentParser(description="Build the deterministic V6.2 canonical archive.")
    parser.add_argument(
        "--output",
        type=Path,
        default=module_root / "frozen" / "two_host_v6_2_canonical_public_20260809.zip",
    )
    args = parser.parse_args()

    entries: dict[str, bytes] = {
        "README.md": (module_root / "CANONICAL_README.md").read_bytes(),
        "verify_canonical_release.py": (module_root / "verify_canonical_release.py").read_bytes(),
    }
    for module in MODULES:
        source = artifact_root / module
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.name == "MANIFEST.sha256" or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(source).as_posix()
            entries[f"modules/{module}/{relative}"] = path.read_bytes()

    manifest = "".join(f"{sha256(data)}  {name}\n" for name, data in sorted(entries.items())).encode("ascii")
    entries["MANIFEST.sha256"] = manifest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    print(f"CANONICAL_FILES={len(entries)}")
    print(f"CANONICAL_ARCHIVE_SHA256={sha256(args.output.read_bytes())}")
    print("CANONICAL_ARCHIVE=BUILT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
