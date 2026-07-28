#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
ENV = os.environ.copy()
ENV.setdefault("NPM_CONFIG_CACHE", str(RUNTIME / "npm-cache"))
ENV.setdefault("NPM_CONFIG_LOGS_DIR", str(RUNTIME / "npm-logs"))
ENV.setdefault("XDG_CONFIG_HOME", str(RUNTIME / "xdg-config"))
ENV.setdefault("XDG_CACHE_HOME", str(RUNTIME / "xdg-cache"))
ENV.setdefault("XDG_DATA_HOME", str(RUNTIME / "xdg-data"))
NPM = "npm.cmd" if os.name == "nt" else "npm"


def run(*command: str) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=ENV, check=True)


RUNTIME.mkdir(exist_ok=True)
run(NPM, "ci", "--no-audit", "--no-fund")
run(NPM, "run", "typecheck")
run(NPM, "test")
run(NPM, "run", "scenarios")
run(sys.executable, "scripts/verify-results.py")
run(sys.executable, "scripts/build-manifest.py", "--check")
