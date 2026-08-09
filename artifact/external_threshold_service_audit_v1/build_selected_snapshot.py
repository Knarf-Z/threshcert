from __future__ import annotations

import argparse
import shutil
import subprocess
import zipfile
from pathlib import Path


COMMIT = "547a9646d929f5f035b054bef94720c5712448c5"
TAG = "v7.6.1"
FILES = (
    "LICENSE",
    "pyproject.toml",
    "nucypher/network/server.py",
    "nucypher/characters/lawful.py",
    "nucypher/blockchain/eth/actors.py",
    "nucypher/crypto/powers.py",
    "nucypher/crypto/ferveo/dkg.py",
    "nucypher/network/decryption.py",
    "nucypher/network/middleware.py",
    "nucypher/utilities/concurrency.py",
)
ZIP_TIMESTAMP = (2026, 8, 9, 0, 0, 0)


def git(upstream: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(upstream), *args], text=True, encoding="utf-8"
    ).strip()


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Build the deterministic selected-source snapshot.")
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "frozen" / "nucypher_v7_6_1_selected_source.zip",
    )
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    if git(upstream, "rev-parse", "HEAD") != COMMIT:
        raise SystemExit("upstream commit mismatch")
    if git(upstream, "describe", "--tags", "--exact-match") != TAG:
        raise SystemExit("upstream tag mismatch")
    missing = [name for name in FILES if not (upstream / name).is_file()]
    if missing:
        raise SystemExit(f"missing selected files: {missing}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(FILES):
            info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (upstream / name).read_bytes())
    shutil.copyfile(upstream / "LICENSE", root / "LICENSE.AGPL-3.0")
    print(f"SELECTED_SOURCE_FILES={len(FILES)}")
    print("SELECTED_SOURCE_SNAPSHOT=BUILT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
