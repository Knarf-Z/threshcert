#!/usr/bin/env python3
"""Reproduce only the three extended experiment groups."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_extended_certificate_experiments.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    expected = (
        ROOT / "expected" / "extended_certificate_summary.txt"
    ).read_text(encoding="utf-8")
    if completed.stdout != expected:
        raise SystemExit("extended experiment summary mismatch")

    print(completed.stdout, end="")
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        check=True,
    )
    print("extended_experiments=PASS")


if __name__ == "__main__":
    main()
