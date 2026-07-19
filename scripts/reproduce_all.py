#!/usr/bin/env python3
"""Run every deterministic artifact check from one entry point."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str, capture: bool = False) -> str:
    completed = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )
    return completed.stdout if capture else ""


def assert_expected(actual: str, expected_name: str) -> None:
    expected = (ROOT / "expected" / expected_name).read_text(encoding="utf-8")
    if actual != expected:
        raise SystemExit(f"output mismatch for expected/{expected_name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-scaling",
        action="store_true",
        help="also rerun the machine-specific wall-clock benchmark",
    )
    args = parser.parse_args()

    run("scripts/verify_manifest.py")
    run("scripts/run_controlled_checks.py")
    production_audit_output = run(
        "scripts/run_production_evidence_audit.py",
        capture=True,
    )
    assert_expected(production_audit_output, "production_evidence_audit.txt")

    public_output = run(
        "scripts/verify_certificate.py",
        "--snapshot",
        "data/shutter_keyper_snapshot.json",
        "--ledger",
        "data/evidence_ledger_public_only.csv",
        "--target",
        "10000",
        capture=True,
    )
    assert_expected(public_output, "public_only.txt")

    positive_output = run(
        "scripts/verify_certificate.py",
        "--snapshot",
        "data/shutter_keyper_snapshot.json",
        "--ledger",
        "data/evidence_ledger_controlled_positive.csv",
        "--target",
        "10000",
        capture=True,
    )
    assert_expected(positive_output, "controlled_positive.txt")

    chiado_certificate_output = run(
        "deployment/scripts/verify_chiado_certificate.py",
        capture=True,
    )
    assert_expected(chiado_certificate_output, "chiado_execution_certificate.txt")

    lattice_output = run("scripts/run_lattice_mobius_experiments.py", capture=True)
    assert_expected(lattice_output, "lattice_mobius_summary.txt")

    penalty_output = run("scripts/run_penalty_certificate_checks.py", capture=True)
    assert_expected(penalty_output, "penalty_summary.txt")

    dune_output = run("scripts/run_dune_calibration_checks.py", capture=True)
    assert_expected(dune_output, "dune_summary.txt")
    run("scripts/summarize_scaling_repeats.py")
    run("-m", "unittest", "discover", "-s", "tests", "-v")

    if args.include_scaling:
        run("scripts/run_scaling_benchmark.py")

    run("scripts/verify_manifest.py")

    print("all_deterministic_checks=PASS")
    print(f"machine_scaling_rerun={'YES' if args.include_scaling else 'NO'}")


if __name__ == "__main__":
    main()
