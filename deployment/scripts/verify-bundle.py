#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN = "d143fffcf51f85b30375134d2d29756417f333b9"


def require(path: str, needle: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if needle not in text:
        raise SystemExit(f"{path} is missing required content: {needle}")


def main() -> None:
    required = [
        "contracts/BondedKeyperSlasher.sol",
        "rolling-shutter/evidence-exporter/main.go",
        "rolling-shutter/evidence-exporter/main_test.go",
        "rolling-shutter/docker-compose.7.yml",
        "scripts/deploy.ts",
        "scripts/open-release.ts",
        "scripts/submit-evidence.ts",
        "SECURITY.md",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"missing required files: {missing}")

    require("contracts/BondedKeyperSlasher.sol", "COMMITTEE_SIZE = 7")
    require("contracts/BondedKeyperSlasher.sol", "THRESHOLD = 4")
    require("rolling-shutter/prepare-upstream.sh", PIN)
    require("rolling-shutter/evidence-exporter/main.go", PIN)
    compose = (ROOT / "rolling-shutter/docker-compose.7.yml").read_text(encoding="utf-8")
    for index in range(3, 7):
        for service in (f"keyper-{index}:", f"chain-{index}-validator:"):
            if service not in compose:
                raise SystemExit(f"compose overlay is missing {service}")

    forbidden_files = {".env", "id_rsa", "id_ed25519"}
    ignored_parts = {"node_modules", "artifacts", "cache", "runtime", "upstream", ".idea", ".vscode"}
    leaked = []
    for path in ROOT.rglob("*"):
        if any(part in ignored_parts for part in path.parts):
            continue

        try:
            is_file = path.is_file()
        except OSError as exc:
            raise SystemExit(
                f"could not inspect {path.relative_to(ROOT)}: {exc}"
            ) from exc

        if not is_file:
            continue

        if path.name in forbidden_files or path.suffix in {".pem", ".key"}:
            leaked.append(str(path.relative_to(ROOT)))
    if leaked:
        raise SystemExit(f"forbidden secret-bearing files: {leaked}")
    print("deployment_bundle_static_checks=PASS")


if __name__ == "__main__":
    main()
