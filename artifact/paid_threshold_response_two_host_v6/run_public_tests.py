#!/usr/bin/env python3
"""Run the V6 tests against the privacy-scrubbed public ZIP layout."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "frozen" / "two_host_execution_evidence.v68.public.zip"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ptr-v6-public-tests-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(ARCHIVE, "r") as archive:
            archive.extractall(root)
        project_results = root / "project" / "results"
        project_results.mkdir(parents=True, exist_ok=True)
        # The scrubbed ZIP stores public evidence objects beside project/ so
        # source files remain separated from run evidence. The original tests
        # expect this one untrusted inventory at project/results; copy it only
        # inside the disposable test tree without changing the frozen archive.
        shutil.copy2(
            root / "results" / "restricted_source_inventory.v2.json",
            project_results / "restricted_source_inventory.v2.json",
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ],
            cwd=root / "project",
            check=True,
        )
    print("TWO_HOST_V6_PUBLIC_TESTS=PASS")


if __name__ == "__main__":
    main()
