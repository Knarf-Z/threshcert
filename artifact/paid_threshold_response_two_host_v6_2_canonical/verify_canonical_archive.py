from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


EXPECTED_SHA256 = "174F1203890B8A032B45FB99FD76BB685D439F9D055C1F446E53A9A2E7F16C92"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> int:
    root = Path(__file__).resolve().parent
    archive_path = root / "frozen" / "two_host_v6_2_canonical_public_20260809.zip"
    actual = sha256(archive_path.read_bytes())
    if actual != EXPECTED_SHA256:
        print("TWO_HOST_V6_2_CANONICAL_ARCHIVE=FAIL")
        print(f"- archive digest mismatch: {actual}")
        return 1

    with tempfile.TemporaryDirectory(prefix="canonical_verify_", dir=root) as temporary:
        destination = Path(temporary).resolve()
        with zipfile.ZipFile(archive_path) as archive:
            for name in archive.namelist():
                parts = PurePosixPath(name).parts
                if not parts or name.startswith("/") or ".." in parts:
                    print("TWO_HOST_V6_2_CANONICAL_ARCHIVE=FAIL")
                    print(f"- unsafe archive path: {name}")
                    return 1
            archive.extractall(destination)
        completed = subprocess.run(
            [sys.executable, "-B", "verify_canonical_release.py"],
            cwd=destination,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.stderr:
            print(completed.stderr.rstrip())
        if completed.returncode != 0:
            print("TWO_HOST_V6_2_CANONICAL_ARCHIVE=FAIL")
            return completed.returncode

    print(f"CANONICAL_ARCHIVE_SHA256={actual}")
    print("TWO_HOST_V6_2_CANONICAL_ARCHIVE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
