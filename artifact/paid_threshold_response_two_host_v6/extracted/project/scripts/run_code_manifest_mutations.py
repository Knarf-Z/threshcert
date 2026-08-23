from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fidelity_core import load_manifest, verify_tree  # noqa: E402


def copy_frozen_tree(src_root: Path, dst_root: Path, manifest: dict) -> None:
    for rel in manifest["files"]:
        source = src_root / rel
        target = dst_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def find_operator_server(root: Path, manifest: dict) -> Path:
    candidates = [root / rel for rel in manifest["files"] if rel.endswith("operator_server.py")]
    if not candidates:
        raise RuntimeError("operator_server.py is not in the frozen file set")
    return candidates[0]


def find_powershell(root: Path, manifest: dict) -> Path:
    preferred = [root / rel for rel in manifest["files"] if rel.endswith("Start-Operators.ps1")]
    if preferred:
        return preferred[0]
    candidates = [root / rel for rel in manifest["files"] if rel.endswith(".ps1")]
    if not candidates:
        raise RuntimeError("no PowerShell file in frozen file set")
    return candidates[0]


def mutate_hash_drift(root: Path, manifest: dict) -> None:
    path = find_operator_server(root, manifest)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n# fidelity mutation: byte drift\n")


def mutate_new_runtime_file(root: Path, manifest: dict) -> None:
    path = root / "src" / "ptr_v3" / "rogue_extension.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def rogue():\n    return 'undeclared'\n", encoding="utf-8", newline="\n")


def mutate_http_route(root: Path, manifest: dict) -> None:
    path = find_operator_server(root, manifest)
    text = path.read_text(encoding="utf-8")
    needle = 'if self.path != "/health":'
    if needle not in text:
        raise RuntimeError("could not locate the baseline /health guard")
    replacement = (
        'if self.path == "/leak":\n'
        '                self._send(200, {"error": "fidelity-mutation-leak"})\n'
        '                return\n'
        '            if self.path != "/health":'
    )
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8", newline="\n")
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def mutate_dynamic_exec(root: Path, manifest: dict) -> None:
    path = find_operator_server(root, manifest)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\ndef _fidelity_dynamic_exec(expr):\n    return eval(expr)\n")


def mutate_secondary_listener(root: Path, manifest: dict) -> None:
    path = find_operator_server(root, manifest)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "\ndef _fidelity_secondary_listener():\n"
            "    return ThreadingHTTPServer(('127.0.0.1', 9999), build_handler(None))\n"
        )


def mutate_powershell_surface(root: Path, manifest: dict) -> None:
    path = find_powershell(root, manifest)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write('\nInvoke-Expression "Write-Host fidelity-mutation"\n')


def run_case(src_root: Path, manifest: dict, digest: str, name: str, mutate, target_check: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"ptr_{name}_") as temp:
        root = Path(temp)
        copy_frozen_tree(src_root, root, manifest)
        mutate(root, manifest)
        result = verify_tree(root, manifest, expected_manifest_digest=digest)
        target_failed = result["checks"].get(target_check) is False
        return {
            "mutation": name,
            "expected_target_check": target_check,
            "target_failed": target_failed,
            "overall_status": result["status"],
            "caught": result["status"] == "FAIL" and target_failed,
            "failed_checks": sorted(k for k, v in result["checks"].items() if not v),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run code-to-manifest adversarial mutation matrix.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=ROOT / "config" / "code_manifest.v1.json")
    parser.add_argument("--digest", type=Path, default=ROOT / "config" / "code_manifest.v1.sha256")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "code_manifest_mutation_matrix.v1.json")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    digest = args.digest.read_text(encoding="ascii").strip().upper()
    baseline = verify_tree(args.root.resolve(), manifest, expected_manifest_digest=digest)
    if baseline["status"] != "PASS":
        print("BASELINE_CODE_MANIFEST_BINDING=FAIL")
        print("Refusing to interpret mutations against a drifting baseline.")
        return 2

    cases = [
        ("byte_hash_drift", mutate_hash_drift, "FILE_HASHES_EXACT"),
        ("undeclared_runtime_file", mutate_new_runtime_file, "FILE_SET_EXACT"),
        ("undeclared_http_route", mutate_http_route, "SURFACE_HTTP_ROUTES_EXACT"),
        ("dynamic_exec", mutate_dynamic_exec, "NO_DYNAMIC_EXEC"),
        ("secondary_listener", mutate_secondary_listener, "SURFACE_SERVER_SITES_EXACT"),
        ("powershell_dynamic_execution", mutate_powershell_surface, "SURFACE_POWERSHELL_SENSITIVE_SITES_EXACT"),
    ]
    rows = [run_case(args.root.resolve(), manifest, digest, name, fn, target) for name, fn, target in cases]
    passed = all(row["caught"] for row in rows)
    record = {
        "schema": "ptr-code-manifest-mutation-matrix/v1",
        "baseline_manifest_sha256": digest,
        "baseline_status": baseline["status"],
        "mutations": rows,
        "caught": sum(1 for row in rows if row["caught"]),
        "total": len(rows),
        "status": "PASS" if passed else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    for row in rows:
        print(f"MUTATION_{row['mutation'].upper()}={'CAUGHT' if row['caught'] else 'MISSED'}")
    print(f"MUTATIONS_CAUGHT={record['caught']}/{record['total']}")
    print(f"CODE_MANIFEST_MUTATION_MATRIX={record['status']}")
    print(f"CODE_MANIFEST_MUTATION_RESULT={args.output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
