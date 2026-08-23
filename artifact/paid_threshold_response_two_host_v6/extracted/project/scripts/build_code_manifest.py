from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fidelity_core import build_manifest, write_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze a code-to-manifest fidelity baseline for PTR two-host v4.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=ROOT / "config" / "code_manifest.v1.json")
    parser.add_argument("--digest", type=Path, default=ROOT / "config" / "code_manifest.v1.sha256")
    parser.add_argument("--force", action="store_true", help="replace an existing frozen baseline")
    args = parser.parse_args()

    if (args.manifest.exists() or args.digest.exists()) and not args.force:
        print("REFUSING_TO_OVERWRITE_FROZEN_CODE_MANIFEST")
        print("Use --force only after an intentional code revision; never during verification.")
        return 2

    manifest = build_manifest(args.root.resolve())
    digest = write_manifest(manifest, args.manifest, args.digest)
    print(f"CODE_MANIFEST={args.manifest}")
    print(f"CODE_MANIFEST_SHA256={digest}")
    print(f"FILES_PINNED={len(manifest['files'])}")
    routes = sorted({x['route'] for x in manifest['surface']['http_routes']})
    print("PUBLIC_HTTP_ROUTES=" + ",".join(routes))
    print(f"HANDLER_METHODS={len(manifest['surface']['handler_methods'])}")
    print(f"SERVER_CONSTRUCTOR_SITES={len(manifest['surface']['server_sites'])}")
    print("CODE_MANIFEST_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
