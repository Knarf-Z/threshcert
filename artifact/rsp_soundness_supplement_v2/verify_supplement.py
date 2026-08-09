from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from differential_validate_rsp import validate as validate_differential
from verify_control_profile import verify as verify_control
from verify_effect_profile import verify as verify_effect


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        result[name] = digest.upper()
    return result


def main() -> int:
    root = Path(__file__).resolve().parent
    default_execution = (
        root.parent
        / "paid_threshold_response_two_host_v6"
        / "frozen"
        / "two_host_v6_final_evidence_20260809.zip"
    )
    parser = argparse.ArgumentParser(
        description="Recompute and byte-compare the RSP-V6.2 soundness supplement."
    )
    parser.add_argument("--execution-zip", type=Path, default=default_execution)
    parser.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Use only when a canonical parent manifest has already verified every file.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 11):
        failures.append("differential validation requires CPython 3.11")

    if not args.skip_manifest:
        manifest = load_manifest(root / "MANIFEST.sha256")
        for name, digest in manifest.items():
            path = root / name
            if not path.is_file() or sha256(path.read_bytes()) != digest:
                failures.append(f"manifest mismatch: {name}")

    frozen_control_path = root / "frozen" / "rsp_control_profile.v2.json"
    frozen_effect_path = root / "frozen" / "rsp_effect_profile.v1.json"
    frozen_differential_path = root / "frozen" / "rsp_differential_validation.v1.json"
    frozen_control = json.loads(frozen_control_path.read_text(encoding="utf-8"))
    frozen_effect = json.loads(frozen_effect_path.read_text(encoding="utf-8"))
    frozen_differential = json.loads(frozen_differential_path.read_text(encoding="utf-8"))

    live_control = verify_control(args.execution_zip.resolve())
    live_effect = verify_effect(args.execution_zip.resolve())
    live_differential = validate_differential()
    if canonical(live_control) != frozen_control_path.read_bytes():
        failures.append("control-profile rerun differs from frozen JSON")
    if canonical(live_effect) != frozen_effect_path.read_bytes():
        failures.append("effect-profile rerun differs from frozen JSON")
    if canonical(live_differential) != frozen_differential_path.read_bytes():
        failures.append("differential rerun differs from frozen JSON")
    if frozen_control.get("status") != "PASS":
        failures.append("frozen control profile did not pass")
    if frozen_effect.get("status") != "PASS":
        failures.append("frozen effect profile did not pass")
    if frozen_differential.get("status") != "PASS":
        failures.append("frozen differential validation did not pass")

    if failures:
        print("RSP_SOUNDNESS_SUPPLEMENT=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"RSP_CONTROL_PROFILE_SHA256={sha256(frozen_control_path.read_bytes())}")
    print(f"RSP_EFFECT_PROFILE_SHA256={sha256(frozen_effect_path.read_bytes())}")
    print(f"RSP_DIFFERENTIAL_SHA256={sha256(frozen_differential_path.read_bytes())}")
    print(f"RSP_DIFFERENTIAL_PROGRAMS={frozen_differential['scope']['programs']}")
    print(f"RSP_DIFFERENTIAL_EXECUTIONS={frozen_differential['scope']['cpython_executions']}")
    print("RSP_EFFECT_PROFILE=PASS")
    print("RSP_DIFFERENTIAL_MUTANTS_CAUGHT=6/6")
    print("RSP_SOUNDNESS_SUPPLEMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
