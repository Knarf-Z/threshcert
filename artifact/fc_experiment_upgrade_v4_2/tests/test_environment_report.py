from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from environment_report import package_version


def test_environment_version_matches_version_file() -> None:
    assert package_version() == (ROOT / "VERSION").read_text(
        encoding="utf-8"
    ).strip()
