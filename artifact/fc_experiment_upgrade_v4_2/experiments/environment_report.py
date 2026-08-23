from __future__ import annotations

import importlib.metadata
import os
import platform
import sys

from common import RESULTS, ROOT, ensure_results, write_json


PACKAGES = ("numpy", "scipy", "pytest")
DEFAULT_SEEDS = [20260725, 20260726, 20260727, 20260728, 20260729]


def package_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def main() -> None:
    ensure_results()
    package_versions = {}
    for package in PACKAGES:
        try:
            package_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            package_versions[package] = None

    write_json(
        RESULTS / "environment.json",
        {
            "package_version": package_version(),
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
            },
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "logical_cpu_count": os.cpu_count(),
            },
            "packages": package_versions,
            "replacement_hull_defaults": {
                "seeds": DEFAULT_SEEDS,
                "repetitions_per_class_per_scale": 60,
                "tolerance": 1e-8,
            },
        },
    )


if __name__ == "__main__":
    main()
