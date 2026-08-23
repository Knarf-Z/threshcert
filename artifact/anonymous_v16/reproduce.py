#!/usr/bin/env python3
"""One-command anonymous reproduction for the v16 experiment claim."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
EVM = ROOT / "artifact" / "joint_incidence_refinement"
POSITIVE = ROOT / "artifact" / "ope_process_positive"


def run(*arguments: str, cwd: Path = ROOT) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("Node.js/npm and Python 3.11+ are required")

    run(
        sys.executable,
        "artifact/reviewer_revision_v77/verify_completeness_certificates_v1.py",
        "--output",
        "reviewer_revision_v77/results/completeness_certificates.v1.json",
        "--verify",
    )
    run(
        sys.executable,
        "artifact/reviewer_revision_v77/test_completeness_negative_controls_v1.py",
        "--root",
        "artifact",
        "--output",
        "reviewer_revision_v77/results/completeness_negative_controls.v15.json",
        "--verify",
    )
    run(
        sys.executable,
        "check_toy_v15.py",
        "--verify",
        cwd=ROOT / "artifact" / "finite_toy_delivery_extension",
    )
    run(
        sys.executable,
        "check_fixture_v2.py",
        "--verify",
        cwd=ROOT / "artifact" / "process_route_stress_fixture",
    )
    if not args.skip_install:
        run(npm, "ci", "--no-audit", "--no-fund", cwd=EVM)
    run(npm, "run", "typecheck", cwd=EVM)
    run(npm, "run", "process:positive:capture", cwd=EVM)
    run(npm, "run", "process:positive:auth", cwd=EVM)
    run(sys.executable, "run_positive_certificate.py", "--verify", cwd=POSITIVE)
    run(sys.executable, "verify_process_certificate.py", cwd=POSITIVE)
    run(sys.executable, "benchmark_certificate_verifier.py", "--verify", cwd=POSITIVE)
    print("ANONYMOUS_V16_AUTHENTICATED_RELATIVE_PROCESS_CERTIFICATE=PASS")


if __name__ == "__main__":
    main()
