#!/usr/bin/env python3
"""Verify the v15 experiment-only certificate extensions.

This entry verifies manifests, the frozen v77 C6 certificate, seven adversarial
extractor controls, the finite explicit-delivery model, and the OPE-anchored
process-v2 fixture. It contains no manuscript source and performs no public-chain
write. Use --full-core to invoke the slower frozen v77 reproduction afterwards.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(*arguments: str, cwd: Path = ROOT) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-core", action="store_true", help="also run reproduce_v77.py")
    args = parser.parse_args()

    node = shutil.which("node")
    if node is None:
        raise SystemExit("v15 experiment verification requires Node.js 20+ and Python 3.11+")

    run(node, "artifact/build_manifest.mjs", "--check")
    run(sys.executable, "scripts/verify_manifest.py")
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
    if args.full_core:
        run(sys.executable, "reproduce_v77.py")
    print("V15_EXPERIMENT_CERTIFICATES=PASS")


if __name__ == "__main__":
    main()
