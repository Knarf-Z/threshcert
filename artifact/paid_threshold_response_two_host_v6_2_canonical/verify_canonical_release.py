from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        if name in result:
            raise ValueError(f"duplicate manifest path: {name}")
        result[name] = digest.upper()
    return result


def run(label: str, command: list[str], cwd: Path) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = completed.stdout.rstrip()
    print(f"--- {label} ---")
    if output:
        print(output)
    return completed.returncode == 0, output


def main() -> int:
    root = Path(__file__).resolve().parent
    failures: list[str] = []
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 11):
        failures.append("canonical verification requires CPython 3.11")

    manifest = load_manifest(root / "MANIFEST.sha256")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "MANIFEST.sha256" and "__pycache__" not in path.parts
    }
    if set(manifest) != actual:
        failures.append(
            f"manifest coverage mismatch: missing={sorted(actual - set(manifest))}, "
            f"extra={sorted(set(manifest) - actual)}"
        )
    for name, digest in manifest.items():
        path = root / name
        if not path.is_file() or sha256(path.read_bytes()) != digest:
            failures.append(f"manifest mismatch: {name}")

    if failures:
        print("TWO_HOST_V6_2_CANONICAL_VERIFICATION=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    node_ok, node_output = run(
        "frozen two-host evidence",
        ["node", "modules/paid_threshold_response_two_host_v6/verify_two_host_v6.mjs"],
        root,
    )
    rsp_ok, rsp_output = run(
        "RSP-V6.2 soundness supplement",
        [
            sys.executable,
            "-B",
            "modules/rsp_soundness_supplement_v2/verify_supplement.py",
            "--skip-manifest",
        ],
        root,
    )
    external_ok, external_output = run(
        "external threshold-service audit",
        [
            sys.executable,
            "-B",
            "modules/external_threshold_service_audit_v1/verify_external_audit.py",
            "--skip-manifest",
        ],
        root,
    )
    if not node_ok or "TWO_HOST_V6_PUBLIC_VERIFICATION=PASS" not in node_output:
        failures.append("frozen two-host verifier failed")
    if not rsp_ok or "RSP_SOUNDNESS_SUPPLEMENT=PASS" not in rsp_output:
        failures.append("RSP-V6.2 supplement failed")
    if not external_ok or "EXTERNAL_THRESHOLD_SERVICE_AUDIT=UNKNOWN" not in external_output:
        failures.append("external audit did not reproduce the verified UNKNOWN result")

    if failures:
        print("TWO_HOST_V6_2_CANONICAL_VERIFICATION=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("CANONICAL_MANIFEST_COVERAGE=PASS")
    print("TWO_HOST_V6_2_CANONICAL_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
