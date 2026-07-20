#!/usr/bin/env python3
"""Single entry point chaining every offline, deterministic reproduction layer.

The bundle has four independently runnable reproduction layers documented
across three different READMEs: ``scripts/reproduce_all.py`` (the original
certificate/lattice/Mobius/Dune/deployment-pilot experiments plus the
production evidence audit and Gnosis counterfactual), the standalone
committee-shape sweep, ``extended_experiments/reproduce_extended.py``
(scalability/sensitivity/baseline studies), and the ``verification_scripts/``
from-scratch reimplementation. Each keeps working on its own; this just
collapses all four into one command for a reviewer who wants a single PASS
line. Live network checks (``scripts/verify_production_snapshot_live.py``,
``npm run verify:chiado:live``) and the Node/Hardhat deployment test suite
are intentionally not included here -- they need a reachable RPC endpoint or
Node.js rather than only the Python standard library, and remain documented
as separate steps in ``README.md`` and ``deployment/README.md``.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(*arguments: str, cwd: Path = ROOT) -> None:
    subprocess.run([sys.executable, *arguments], cwd=cwd, check=True)


def main() -> None:
    run("scripts/reproduce_all.py")
    run("scripts/run_generalized_committee_sweep.py")
    run("extended_experiments/reproduce_extended.py")

    verification_dir = ROOT / "verification_scripts"
    for script in (
        "test_equivalence.py",
        "reproduce_paper_numbers.py",
        "hardening_and_greedy.py",
        "instability.py",
    ):
        run(script, cwd=verification_dir)

    run("scripts/verify_chiado_certificate.py", cwd=ROOT / "deployment")
    run("scripts/verify_manifest.py")

    print("everything=PASS")


if __name__ == "__main__":
    main()
