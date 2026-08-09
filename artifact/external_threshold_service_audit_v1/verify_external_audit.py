from __future__ import annotations

import argparse
import ast
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "external-threshold-service-source-audit/v1"
UPSTREAM_COMMIT = "547a9646d929f5f035b054bef94720c5712448c5"
UPSTREAM_TAG = "v7.6.1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def definitions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def exactly_one(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [node for node in definitions(tree) if node.name == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name}, found {len(matches)}")
    return matches[0]


def calls(node: ast.AST) -> set[str]:
    return {call_name(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)}


def has_broad_exception(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.ExceptHandler)
        and isinstance(child.type, ast.Name)
        and child.type.id == "Exception"
        for child in ast.walk(node)
    )


def load_snapshot(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if not name.endswith("/")
        }


def audit(snapshot: Path, metadata_path: Path) -> dict[str, Any]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    entries = load_snapshot(snapshot)
    source_names = [name for name in entries if name.endswith(".py")]
    trees = {
        name: ast.parse(entries[name].decode("utf-8"), filename=name)
        for name in source_names
    }

    server = trees["nucypher/network/server.py"]
    lawful = trees["nucypher/characters/lawful.py"]
    actors = trees["nucypher/blockchain/eth/actors.py"]
    powers = trees["nucypher/crypto/powers.py"]
    decryption = trees["nucypher/network/decryption.py"]

    route = exactly_one(server, "threshold_decrypt")
    handle = exactly_one(lawful, "handle_threshold_decryption_request")
    actor_producer = exactly_one(actors, "_produce_decryption_share_for_request")
    power_producer = exactly_one(powers, "produce_decryption_share")

    route_decorators = [ast.unparse(item) for item in route.decorator_list]
    route_calls = calls(route)
    handle_calls = calls(handle)
    actor_calls = calls(actor_producer)
    power_calls = calls(power_producer)
    decryption_calls = calls(decryption)
    power_source = ast.unparse(power_producer)

    facts = {
        "UPSTREAM_IDENTITY_PINNED": (
            metadata.get("commit") == UPSTREAM_COMMIT
            and metadata.get("tag") == UPSTREAM_TAG
            and metadata.get("repository") == "https://github.com/nucypher/nucypher"
        ),
        "FLASK_DECRYPT_ROUTE_PRESENT": any(
            "rest_app.route" in item and "/decrypt" in item for item in route_decorators
        ),
        "METRICS_CONTEXT_DECORATOR_PRESENT": any(
            "DECRYPTION_REQUEST_SUMMARY.time" in item for item in route_decorators
        ),
        "ROUTE_HAS_DYNAMIC_FRAMEWORK_AND_RESPONSE_SITES": {
            "EncryptedThresholdDecryptionRequest.from_bytes",
            "this_node.handle_threshold_decryption_request",
            "Response",
        } <= route_calls,
        "ROUTE_HAS_BROAD_EXCEPTION": has_broad_exception(route),
        "APPLICATION_HANDLER_CHAIN_PRESENT": {
            "self.decrypt_threshold_decryption_request",
            "self._produce_decryption_share_for_request",
            "self._encrypt_decryption_share",
        } <= handle_calls,
        "ACTOR_AUTHORIZATION_AND_SHARE_CHAIN_PRESENT": (
            "self._verify_decryption_request_authorization" in actor_calls
            and "self.produce_decryption_share" in actor_calls
        ),
        "NATIVE_DKG_BOUNDARY_PRESENT": (
            "dkg.produce_decryption_share" in power_calls and "_privkey" in power_source
        ),
        "WORKER_POOL_CALLBACK_SURFACE_PRESENT": (
            "WorkerPool" in decryption_calls or "WorkerPool" in ast.unparse(decryption)
        ),
        "AGPL_LICENSE_INCLUDED": "GNU AFFERO GENERAL PUBLIC LICENSE" in entries["LICENSE"].decode(
            "utf-8", errors="replace"
        ),
    }

    obligations = {
        "LC1": {
            "status": "UNKNOWN",
            "reason": (
                "The Flask decorator, request proxy, metrics context, and native share producer "
                "are outside the closed RSP call-and-effect fragment; producer completeness is not proved."
            ),
        },
        "LC3": {
            "status": "UNKNOWN",
            "reason": (
                "The operator private key crosses the nucypher_core DKG boundary, so secret "
                "confinement cannot be discharged from the selected Python source."
            ),
        },
        "LC5": {
            "status": "UNKNOWN",
            "reason": (
                "Ritual, handover, blockchain, storage, and worker-pool lifecycle state are not "
                "closed under the restricted source model."
            ),
        },
        "LC7": {
            "status": "UNKNOWN",
            "reason": (
                "Flask response construction, decorators, broad exception handling, callbacks, "
                "and network sinks do not admit the program-specific delivery-root proof."
            ),
        },
    }

    return {
        "schema": SCHEMA,
        "verification_status": "PASS" if all(facts.values()) else "FAIL",
        "audit_status": "UNKNOWN",
        "subject": {
            "name": "NuCypher Threshold Access Control node runtime",
            "repository": metadata["repository"],
            "release": metadata["release"],
            "tag": metadata["tag"],
            "commit": metadata["commit"],
            "snapshot_sha256": sha256(snapshot.read_bytes()),
            "selected_files": {name: sha256(data) for name, data in sorted(entries.items())},
        },
        "structural_facts": facts,
        "obligations": obligations,
        "payment_bridge": {
            "status": "NOT_AUDITED",
            "reason": "The target is a threshold-access service, not the paper's contingent-payment instance.",
        },
        "interpretation": (
            "The verifier reproduces a fail-closed UNKNOWN result on independently maintained "
            "real-world threshold-service code. It is not a positive certificate, a third-party "
            "replication, or evidence that the service violates an obligation."
        ),
    }


def load_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        result[name] = digest.upper()
    return result


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Reproduce the pinned external threshold-service audit.")
    parser.add_argument("--snapshot", type=Path, default=root / "frozen" / "nucypher_v7_6_1_selected_source.zip")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Use only when a canonical parent manifest has already verified every file.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    if not args.skip_manifest:
        for name, digest in load_manifest(root / "MANIFEST.sha256").items():
            path = root / name
            if not path.is_file() or sha256(path.read_bytes()) != digest:
                failures.append(f"manifest mismatch: {name}")

    live = audit(args.snapshot.resolve(), root / "UPSTREAM.json")
    frozen_path = root / "frozen" / "nucypher_v7_6_1_source_obligation_audit.v1.json"
    if frozen_path.exists() and canonical(live) != frozen_path.read_bytes():
        failures.append("live external audit differs from frozen JSON")
    if live["verification_status"] != "PASS" or live["audit_status"] != "UNKNOWN":
        failures.append("expected structurally verified fail-closed UNKNOWN result")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical(live))

    if failures:
        print("EXTERNAL_AUDIT_VERIFICATION=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"EXTERNAL_SERVICE=nucypher/nucypher@{UPSTREAM_TAG}")
    for name in ("LC1", "LC3", "LC5", "LC7"):
        print(f"{name}_SOURCE_STATUS={live['obligations'][name]['status']}")
    print("EXTERNAL_THRESHOLD_SERVICE_AUDIT=UNKNOWN")
    print("EXTERNAL_AUDIT_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
