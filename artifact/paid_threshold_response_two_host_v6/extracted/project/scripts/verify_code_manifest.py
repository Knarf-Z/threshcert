from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fidelity_core import load_manifest, print_result, verify_tree  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PTR code-to-manifest fidelity without importing experiment code.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=ROOT / "config" / "code_manifest.v1.json")
    parser.add_argument("--digest", type=Path, default=ROOT / "config" / "code_manifest.v1.sha256")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "code_manifest_binding.v1.json")
    args = parser.parse_args()

    if not args.manifest.exists() or not args.digest.exists():
        print("CODE_MANIFEST_BASELINE_MISSING")
        return 2
    manifest = load_manifest(args.manifest)
    expected = args.digest.read_text(encoding="ascii").strip().upper()
    result = verify_tree(args.root.resolve(), manifest, expected_manifest_digest=expected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print_result(result)
    print(f"CODE_MANIFEST_BINDING_RESULT={args.output}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
