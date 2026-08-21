#!/usr/bin/env python3
"""Single clean entry for the public v77 review artifact.

The script verifies committed manifests before installing the locked EVM
dependencies, then executes every public certificate, control, EVM,
deployment-admission, and refinement check used by the v77 workflow.  It does
not contact a public chain and does not contain or reproduce the manuscript.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EVM = ROOT / "artifact" / "joint_incidence_refinement"


def run(*arguments: str, cwd: Path = ROOT) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=cwd, check=True)


def main() -> None:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if npm is None or node is None:
        raise SystemExit("v77 reproduction requires Node.js/npm and Python 3.11+")

    run(node, "artifact/build_manifest.mjs", "--check")
    run(sys.executable, "scripts/verify_manifest.py")
    run(npm, "ci", "--no-audit", "--no-fund", cwd=EVM)
    run(npm, "run", "typecheck", cwd=EVM)
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
    )
    run(npm, "test", cwd=EVM)
    run(
        sys.executable,
        "artifact/global_named_acquirer_toy/verify_global_named_acquirer_toy.py",
        "--verify",
        "--self-test",
    )
    for command in (
        "admission:verify",
        "admission:negative",
        "refinement:check",
        "prefunded:verify",
    ):
        run(npm, "run", command, cwd=EVM)
    run(sys.executable, "verify_schema_independent.py", cwd=EVM)
    print("v77_public_review_artifact=PASS")


if __name__ == "__main__":
    main()
