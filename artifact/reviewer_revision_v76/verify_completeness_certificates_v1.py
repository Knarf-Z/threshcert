"""Materialize and verify the OPE C6/B5 completeness certificate.

This checker deliberately separates two scopes:

* C6 and contract-local route closure are checked for the admitted OPE runtime.
* deployment-wide B5 remains OPEN because off-contract and unadmitted routes are
  not excluded by the supplied evidence.

The generated JSON contains one finite C6 record for every admitted root/terminal
pair.  It is deterministic: no timestamp or host-specific absolute path is
embedded in the output.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any


SCHEMA = "fc-c6-b5-completeness-certificate/v1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def credit_roots() -> list[list[int]]:
    roots: list[list[int]] = []
    for digits in itertools.product(range(3), repeat=7):
        if sum(digits[:4]) <= 2 and sum(digits[3:]) <= 2:
            roots.append(list(digits))
    return roots


def terminal_sets() -> list[list[int]]:
    return [list(x) for x in itertools.combinations(range(7), 4)]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} is not a JSON object")
    return value


def build_certificate(root: Path) -> dict[str, Any]:
    candidates = [
        root / "verify_v42_clean" / "joint_incidence_refinement",
        root / "joint_incidence_refinement",
        root / "artifact" / "joint_incidence_refinement",
    ]
    refinement_dir = next((path for path in candidates if path.is_dir()), candidates[0])
    results_dir = refinement_dir / "results"
    paths = {
        "refinement": results_dir / "refinement_certificate.json",
        "obligation_map": results_dir / "refinement_obligation_map.json",
        "halmos": results_dir / "halmos_evm_bridge.json",
        "halmos_log": results_dir / "halmos_evm_bridge.log",
        "deployment": results_dir / "deployment_admission_certificate.json",
        "deployment_negative": results_dir / "deployment_admission_negative.json",
        "contract": refinement_dir / "contracts" / "OverlappingPoolEscrow.sol",
        "artifact": refinement_dir
        / "artifacts"
        / "contracts"
        / "OverlappingPoolEscrow.sol"
        / "OverlappingPoolEscrow.json",
        "harness": refinement_dir / "formal" / "OverlappingPoolEscrowBridge.t.sol",
        "checker": Path(__file__).resolve(),
    }
    for label, path in paths.items():
        require(path.is_file(), f"missing {label}: {path}")

    refinement = load_json(paths["refinement"])
    obligations = load_json(paths["obligation_map"])
    halmos = load_json(paths["halmos"])
    deployment = load_json(paths["deployment"])
    deployment_negative = load_json(paths["deployment_negative"])

    require(refinement.get("schema") == "overlapping-pool-schema-certificate/v7", "bad refinement schema")
    require(obligations.get("status") == "PASS", "refinement obligation map is not PASS")
    require(halmos.get("schema") == "overlapping-pool-halmos-bridge/v6", "bad Halmos schema")
    require(halmos.get("status") == "PASS", "Halmos result is not PASS")
    proof_counts = halmos.get("proofCounts", {})
    require(proof_counts.get("totalProofs") == 82, "expected 82 Halmos obligations")
    require(proof_counts.get("failed") == 0, "Halmos reports a failed obligation")
    require(proof_counts.get("nonemptyBounds") == 0, "Halmos reports an exploration bound")
    require(deployment.get("status") == "PASS", "deployment admission is not PASS")
    require(
        deployment_negative.get("status") == "PASS"
        and deployment_negative.get("totalRejected") == 10,
        "deployment tamper suite did not reject all ten cases",
    )

    input_hashes = {label: sha256_file(path) for label, path in paths.items()}
    artifact_for_hash = load_json(paths["artifact"])
    artifact_for_hash.pop("buildInfoId", None)
    input_hashes["artifact"] = sha256_bytes(canonical_bytes(artifact_for_hash))
    audit = refinement.get("implementationAuditEvidence", {})
    require(input_hashes["contract"] == audit.get("sourceSha256"), "contract hash mismatch")
    require(input_hashes["artifact"] == audit.get("artifactSemanticSha256"), "artifact semantic hash mismatch")
    require(input_hashes["halmos"] == audit.get("halmosCertificateSha256"), "Halmos result hash mismatch")
    require(input_hashes["halmos_log"] == audit.get("halmosTranscriptSha256"), "Halmos log hash mismatch")
    require(
        input_hashes["obligation_map"] == audit.get("refinementObligationMapSha256"),
        "obligation-map hash mismatch",
    )

    roots = credit_roots()
    terminals = terminal_sets()
    require(len(roots) == 117, f"expected 117 roots, found {len(roots)}")
    require(len(terminals) == 35, f"expected 35 terminal sets, found {len(terminals)}")
    require(refinement["finiteCheck"]["admissibleCreditVectors"] == len(roots), "root count mismatch")
    require(refinement["finiteCheck"]["terminalSets"] == len(terminals), "terminal count mismatch")

    proofs = halmos.get("proofs", {})
    path_records: list[dict[str, Any]] = []
    costs: list[int] = []
    for root_index, credits in enumerate(roots):
        root_id = f"r{root_index:03d}"
        for terminal in terminals:
            terminal_code = "".join(str(x) for x in terminal)
            proof_name = f"check_EVMEdge_{terminal_code}"
            proof = proofs.get(proof_name)
            require(isinstance(proof, dict), f"missing reverse proof {proof_name}")
            require(proof.get("bounds") == [], f"nonempty bounds for {proof_name}")
            local_cost = sum(2 - credits[i] for i in terminal)
            require(local_cost >= 4, f"local floor violated at {root_id}/{terminal_code}")
            delivery = {
                "predicate": "four selected on-chain share rights transferred to the exact payer",
                "selected_member_indices": terminal,
                "terminal_mask": sum(1 << i for i in terminal),
            }
            binding = {
                "root_id": root_id,
                "credit_vector": credits,
                "canonical_action": {"entry": "acquireFour(uint8[4])", "arguments": terminal},
                "delivery": delivery,
                "local_cost_units": local_cost,
                "forward_witness": "declared OPE transition equation plus admitted-runtime forward simulation",
                "reverse_witness": proof_name,
            }
            path_records.append(
                {
                    **binding,
                    "reverse_proof_paths": proof.get("paths"),
                    "reverse_proof_bounds": proof.get("bounds"),
                    "binding_sha256": sha256_bytes(canonical_bytes(binding)),
                }
            )
            costs.append(local_cost)

    require(len(path_records) == 4095, f"expected 4095 C6 records, found {len(path_records)}")
    require(len({x["binding_sha256"] for x in path_records}) == 4095, "duplicate C6 bindings")
    require(min(costs) == 4 and max(costs) == 8, "unexpected OPE cost range")
    require(refinement["finiteCheck"]["checkedStateSetPairs"] == len(path_records), "edge count mismatch")
    require(refinement["finiteCheck"]["minimumResidualPayment"] == min(costs), "minimum mismatch")
    require(refinement["finiteCheck"]["maximumResidualPayment"] == max(costs), "maximum mismatch")

    clauses = obligations.get("refinementClauses", {})
    for clause in ("entryClosure", "terminalFamilyCompleteness", "outcomeCompleteness", "backwardRealization"):
        require(clauses.get(clause, {}).get("status") == "PASS", f"{clause} is not PASS")
    mutating = audit.get("mutatingEntryClosure", {})
    require(mutating.get("acquisition") == ["acquireFour(uint8[4])"], "acquisition ABI is not closed")
    require(mutating.get("fallbackOrReceive") == [], "fallback or receive route is present")

    record_digest = sha256_bytes(canonical_bytes(path_records))
    return {
        "schema": SCHEMA,
        "checker_status": "PASS",
        "claim_status": "C6_CONTRACT_LOCAL_PASS__B5_GLOBAL_OPEN",
        "scope": {
            "admitted_runtime": "OverlappingPoolEscrow direct Cancun deployment accepted by the pinned admission checker",
            "unit": "abstract contract-local accounting units",
            "not_claimed": [
                "wei, token, or market price",
                "global named-acquirer net outflow",
                "deployment-wide exclusion of off-contract or unadmitted success routes",
            ],
        },
        "inputs": {
            label: {
                "path": (
                    "reviewer_revision_v76/verify_completeness_certificates_v1.py"
                    if label == "checker"
                    else "joint_incidence_refinement/" + str(path.relative_to(refinement_dir)).replace("\\", "/")
                ),
                "sha256": input_hashes[label],
                "digest_kind": "canonical-json-minus-buildInfoId" if label == "artifact" else "raw-file",
            }
            for label, path in paths.items()
        },
        "c6": {
            "schema": {
                "required_fields": [
                    "root_id",
                    "credit_vector",
                    "canonical_action",
                    "delivery",
                    "local_cost_units",
                    "forward_witness",
                    "reverse_witness",
                    "reverse_proof_bounds",
                    "binding_sha256",
                ],
                "acceptance_rule": "same admitted root/action/delivery/cost binding; reverse proof exists and has empty exploration bounds",
            },
            "status": "PASS",
            "roots": len(roots),
            "terminal_classes": len(terminals),
            "forward_success_paths": len(path_records),
            "reverse_realized_paths": len(path_records),
            "exactness_inclusion": True,
            "minimum_local_cost_units": min(costs),
            "maximum_local_cost_units": max(costs),
            "records_sha256": record_digest,
            "records": path_records,
        },
        "b5": {
            "record_schema": {
                "fields": ["scope", "route_inventory", "refinement_map", "success_digest", "bypass_exclusions"],
                "acceptance_rule": "every success route in the stated scope is mapped, and every bypass class has a checked exclusion",
            },
            "contract_local": {
                "status": "PASS",
                "route_inventory": ["configureCredits(uint256[7])", "acquireFour(uint8[4])", "withdraw()"],
                "success_producing_entry": "acquireFour(uint8[4])",
                "fallback_or_receive": [],
                "terminal_classes": len(terminals),
                "evidence": [
                    "ABI and runtime-opcode closure",
                    "unique success-producing entry and terminal writers",
                    "deployment admission plus ten rejected tamper cases",
                    "entryClosure, terminalFamilyCompleteness, and outcomeCompleteness obligations",
                ],
            },
            "deployment_global": {
                "status": "OPEN",
                "reason": "the certificate quantifies only over the admitted direct runtime; the mechanism universe may contain unadmitted or off-contract success routes",
                "missing_exclusion_classes": [
                    "unadmitted contracts, proxies, upgrades, and alternate deployments",
                    "off-contract delivery or reimbursement routes",
                    "silent leakage and side channels",
                    "beneficial-control and sponsor-funding completions",
                ],
                "required_verdict": "UNKNOWN",
            },
        },
        "tcb": {
            "manual": ["definition of the admitted scope", "interpretation of C6 and B5", "EVM call/storage-isolation lemma"],
            "checker": ["this Python verifier", "existing refinement and deployment checkers"],
            "external": ["Solidity 0.8.28", "Foundry/Hardhat", "Halmos 0.3.3", "Yices 2.6.4", "CPython 3.11"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("results/completeness_certificates.v1.json"))
    parser.add_argument("--verify", action="store_true", help="compare with the existing output instead of rewriting it")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    certificate = build_certificate(root)
    encoded = json.dumps(certificate, indent=2, sort_keys=True) + "\n"
    if args.verify:
        require(output.is_file(), f"missing certificate output: {output}")
        require(output.read_text(encoding="utf-8") == encoded, "certificate does not match deterministic regeneration")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8", newline="\n")
    print("C6_CERTIFICATE=PASS")
    print("C6_PATHS=4095_OF_4095")
    print("C6_LOCAL_COST_RANGE=4..8_ABSTRACT_UNITS")
    print("B5_CONTRACT_LOCAL=PASS")
    print("B5_DEPLOYMENT_GLOBAL=OPEN")
    print("GLOBAL_PAYMENT_VERDICT=UNKNOWN")
    print(f"CERTIFICATE_SHA256={sha256_bytes(encoded.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
