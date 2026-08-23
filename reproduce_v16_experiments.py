#!/usr/bin/env python3
"""Reproduce the v16 base plus the fail-closed P2-star certificate extension."""

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
    parser.add_argument("--full-core", action="store_true")
    args = parser.parse_args()
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("v16 reproduction requires Node.js/npm and Python 3.11+")

    run(sys.executable, "reproduce_v15_experiments.py")
    if not args.skip_install:
        run(npm, "ci", "--no-audit", "--no-fund", cwd=EVM)
    run(npm, "run", "typecheck", cwd=EVM)
    run(npm, "run", "process:positive:capture", cwd=EVM)
    run(npm, "run", "process:positive:auth", cwd=EVM)
    run(
        sys.executable,
        "run_positive_certificate.py",
        "--verify",
        cwd=POSITIVE,
    )
    run(sys.executable, "verify_process_certificate.py", "--verify-mutations", cwd=POSITIVE)
    run(sys.executable, "benchmark_certificate_verifier.py", "--verify", cwd=POSITIVE)
    if args.full_core:
        run(sys.executable, "reproduce_v77.py")
    print("P2STAR_BOUNDARY_MANIFESTS_AND_MUTATIONS=PASS")
    print("RELATIVE_PROCESS_CERTIFICATE=PASS")
    print("OPE_PROCESS_CERTIFICATE_V3=PASS")


if __name__ == "__main__":
    main()
