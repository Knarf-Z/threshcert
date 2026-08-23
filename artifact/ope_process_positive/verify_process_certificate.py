#!/usr/bin/env python3
"""Independent verifier for the authenticated relative-process certificate.

This verifier uses only the Python standard library and does not import the
certificate generator or any service-runtime module. It validates the public
JSON Schema, the two bound input artifacts, route completeness and accounting,
operator/member bindings, Schnorr response signatures, Chaum--Pedersen proofs,
threshold reconstruction, and commitment-valid delivery.
"""

from __future__ import annotations

import argparse
import hashlib
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CERTIFICATE_PATH = HERE / "results" / "ope_process_positive.v3.json"
SCHEMA_PATH = HERE / "schema" / "ope_process_certificate.schema.json"
ROUTES_PATH = REPO / "artifact" / "joint_incidence_refinement" / "results" / "ope_process_routes.v1.json"
C6_PATH = REPO / "artifact" / "reviewer_revision_v77" / "results" / "completeness_certificates.v1.json"
AUTH_VERIFIER = REPO / "artifact" / "joint_incidence_refinement" / "scripts" / "VerifyOpeProcessAuth.mjs"
RUNNER_PATH = HERE / "run_positive_certificate.py"
REFINEMENT_PATH = REPO / "artifact" / "joint_incidence_refinement" / "results" / "refinement_certificate.json"
CONTRACT_SOURCE_PATH = REPO / "artifact" / "joint_incidence_refinement" / "contracts" / "OverlappingPoolEscrow.sol"
MUTATION_RESULTS_PATH = HERE / "results" / "p2star_mutations.v1.json"

_P_HEX = """
FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1
29024E088A67CC74020BBEA63B139B22514A08798E3404DD
EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245
E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED
EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D
C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F
83655D23DCA3AD961C62F356208552BB9ED529077096966D
670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B
E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9
DE2BCBF6955817183995497CEA956AE515D2261898FA0510
15728E5A8AACAA68FFFFFFFFFFFFFFFF
""".replace("\n", "")
P = int(_P_HEX, 16)
Q = (P - 1) // 2
G = 4
UNIT_WEI = 10**18
FIXED_CREDITS = [2, 0, 0, 0, 2, 0, 0]
EXPECTED_VERDICT = "RELATIVE-PROCESS-CERTIFIED(4)"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def int_to_bytes(value: int) -> bytes:
    require(value >= 0, "negative integer encoding")
    return value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")


def encode_parts(parts: Sequence[bytes]) -> bytes:
    return b"".join(len(part).to_bytes(8, "big") + part for part in parts)


def hash_to_int(modulus: int, *parts: bytes) -> int:
    return int.from_bytes(hashlib.sha256(encode_parts(parts)).digest(), "big") % modulus


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_digest(value: Any) -> str:
    return sha256_hex(canonical_json_bytes(value))


def session_id_for_capture_route(route: Mapping[str, Any]) -> str:
    return f"ope-process:{str(route['payment_transaction']['hash']).lower()}"


def debit_id_for_capture_route(capture: Mapping[str, Any], route: Mapping[str, Any]) -> str:
    return ":".join(
        [
            str(capture["chain_id"]),
            str(route["contract"]["address"]).lower(),
            str(route["payment_transaction"]["hash"]).lower(),
        ]
    )


def verify_p2star_boundary(
    certificate: Mapping[str, Any],
    capture: Mapping[str, Any],
    refinement: Mapping[str, Any],
) -> None:
    boundary = certificate["boundary"]
    header = boundary["header"]
    manifests = boundary["manifests"]
    audit = refinement["implementationAuditEvidence"]
    obligations = refinement["obligations"]
    bridge = refinement["bridgeScope"]
    attacker = str(capture["roles"]["attacker"]).lower()
    controller = str(capture["roles"]["service_contract_controller"]).lower()
    members = [str(value).lower() for value in capture["roles"]["committee_member_addresses"]]
    capture_routes = list(capture["routes"])
    expected_sessions = sorted(
        [
            {
                "session_id": session_id_for_capture_route(route),
                "contract_address": str(route["contract"]["address"]).lower(),
                "payment_tx_hash": str(route["payment_transaction"]["hash"]).lower(),
                "horizon_end_block": int(route["finality"]["observed_head_block"]),
            }
            for route in capture_routes
        ],
        key=lambda item: item["session_id"],
    )
    require(boundary["session_records"] == expected_sessions, "P2STAR_SESSION_SET_MISMATCH")
    session_set_digest = json_digest(expected_sessions)
    scope_core = {
        "schema": "ope-p2star-scope/v1",
        "chain_id": int(capture["chain_id"]),
        "resource": str(capture["scope"]["resource"]),
        "accounting_unit": str(capture["scope"]["accounting_unit"]),
        "success_predicate": "first commitment-valid plaintext delivery to the authenticated attacker",
        "process_boundary": "controlled OPE contract plus the seven authenticated operator processes",
    }
    scope_id = f"ope-scope:{json_digest(scope_core)}"
    inventory = certificate["runtime"]["source_inventory"]
    expected_anchors = {
        "capture_sha256": file_sha256(ROUTES_PATH),
        "refinement_certificate_sha256": file_sha256(REFINEMENT_PATH),
        "contract_source_sha256": file_sha256(CONTRACT_SOURCE_PATH),
        "refinement_contract_source_sha256": str(audit["sourceSha256"]),
        "compiled_artifact_semantic_sha256": str(audit["artifactSemanticSha256"]),
        "runtime_source_digest": str(inventory["runtime_source_digest"]),
    }
    require(
        expected_anchors["contract_source_sha256"]
        == expected_anchors["refinement_contract_source_sha256"],
        "P2STAR_SOURCE_ANCHOR_MISMATCH",
    )
    expected_bodies: dict[str, Any] = {
        "control": {
            "attacker_control_accounts": [attacker],
            "payer_accounts": [attacker],
            "requester_accounts": [attacker],
            "recipient_accounts": [attacker],
            "service_controller_accounts": [controller],
            "committee_member_accounts": members,
            "role_separation": "attacker, controller, and seven committee members are pairwise role-disjoint",
            "completeness_basis": [
                "authenticated Hardhat account tuple in the route capture",
                "direct-construction role separation in the refinement certificate",
                "seven signed member/operator bindings",
            ],
        },
        "acquisition_links": {
            "funding_paths": [
                {
                    "path_id": "controller-configuration-funding",
                    "source_role": "service_controller",
                    "destination_role": "ope_contract",
                    "action": "configureCredits(uint256[7])",
                    "attacker_cost_direction": "excluded-service-funding",
                },
                {
                    "path_id": "attacker-acquisition-payment",
                    "source_role": "attacker",
                    "destination_role": "ope_contract",
                    "action": "acquireFour(uint8[4])",
                    "attacker_cost_direction": "boundary-outflow",
                },
            ],
            "return_rebate_paths": [],
            "settlement_paths": [
                {
                    "path_id": "member-credit-withdrawal",
                    "source_role": "ope_contract",
                    "destination_role": "committee_member",
                    "action": "withdraw()",
                    "attacker_cost_direction": "outside-attacker-control",
                }
            ],
            "service_runtime_economic_paths": [],
            "cross_session_value_paths": [],
            "success_universe_anchor": str(bridge["successUniverse"]),
        },
        "settlement_surface": {
            "contract_mutating_entry_points": audit["mutatingEntryClosure"],
            "fallback_or_receive_entry_points": list(audit["mutatingEntryClosure"]["fallbackOrReceive"]),
            "external_value_call_count": int(audit["runtimeOpcodeGuards"]["call"]),
            "value_transfer_entry_points": ["withdraw()"],
            "attacker_return_interfaces": [
                {
                    "entry_point": "withdraw()",
                    "eligibility": "claimable(msg.sender) > 0",
                    "attacker_claimable_at_horizon_wei": 0,
                    "attacker_probe_result": "rejected-on-all-35-sessions",
                }
            ],
            "refund_cancel_rebate_entry_points": [],
            "operator_service_economic_entry_points": [],
            "entry_closure_obligation": str(obligations["implementationEntryClosure"]),
            "opcode_closure_obligation": str(obligations["implementationOpcodeClosure"]),
        },
        "reuse_namespace": {
            "session_id_rule": "ope-process:<lowercase-payment-transaction-hash>",
            "debit_id_rule": "<chain-id>:<contract-address>:<payment-transaction-hash>",
            "debit_allocations": [
                {
                    "session_id": session_id_for_capture_route(route),
                    "underlying_debit_id": debit_id_for_capture_route(capture, route),
                }
                for route in capture_routes
            ],
            "maximum_success_allocations_per_debit": 1,
            "operator_replay_key_fields": [
                "scope_id",
                "header_digest",
                "session_id",
                "operator_id",
                "nonce",
            ],
            "cross_session_reuse_allowed": False,
            "persistent_receipt_and_nonce_state": True,
        },
        "horizon": {
            "kind": "per-session-state-closure",
            "start_event": "successful controller configuration",
            "end_condition": "payment finality, commitment-valid delivery, zero attacker claimable balance, rejected attacker withdrawal probe, and persistent reuse-state check",
            "return_right_disposition": "every authenticated attacker-return interface is terminated, ineligible, or recorded",
            "session_end_blocks": {
                item["session_id"]: item["horizon_end_block"] for item in expected_sessions
            },
            "open_attacker_claims_at_horizon": 0,
        },
    }
    mismatch_codes = {
        "control": "P2STAR_CONTROL_MANIFEST_MISMATCH",
        "acquisition_links": "P2STAR_ACQUISITION_LINK_MANIFEST_MISMATCH",
        "settlement_surface": "P2STAR_SETTLEMENT_SURFACE_MISMATCH",
        "reuse_namespace": "P2STAR_REUSE_NAMESPACE_MISMATCH",
        "horizon": "P2STAR_HORIZON_MANIFEST_MISMATCH",
    }
    for name, expected_body in expected_bodies.items():
        envelope = manifests[name]
        require(envelope["body"] == expected_body, mismatch_codes[name])
        require(envelope["body_digest"] == json_digest(expected_body), f"P2STAR_{name.upper()}_DIGEST_MISMATCH")
    expected_manifest_digests = {
        name: json_digest(body) for name, body in expected_bodies.items()
    }
    expected_header_core = {
        "schema": "ope-p2star-header/v1",
        "scope_id": scope_id,
        "scope": scope_core,
        "session_set_digest": session_set_digest,
        "manifest_digests": expected_manifest_digests,
        "source_anchors": expected_anchors,
        "settlement_horizon_kind": "per-session-state-closure",
    }
    expected_header_digest = json_digest(expected_header_core)
    require(header == {**expected_header_core, "header_digest": expected_header_digest}, "P2STAR_HEADER_MISMATCH")
    for name, envelope in manifests.items():
        require(envelope["scope_id"] == scope_id, f"P2STAR_{name.upper()}_SCOPE_BINDING_MISMATCH")
        require(envelope["header_digest"] == expected_header_digest, f"P2STAR_{name.upper()}_HEADER_BINDING_MISMATCH")
        require(envelope["session_set_digest"] == session_set_digest, f"P2STAR_{name.upper()}_SESSION_BINDING_MISMATCH")


def verify_p2star_route_bindings(
    certificate: Mapping[str, Any],
    capture: Mapping[str, Any],
) -> None:
    header = certificate["boundary"]["header"]
    capture_by_id = {str(route["route_id"]): route for route in capture["routes"]}
    debit_ids: list[str] = []
    session_ids: list[str] = []
    for route in certificate["routes"]:
        captured = capture_by_id[str(route["route_id"])]
        binding = route["p2star_binding"]
        expected_session = session_id_for_capture_route(captured)
        expected_debit = debit_id_for_capture_route(capture, captured)
        require(binding["session_id"] == route["order_id"] == expected_session, "P2STAR_ROUTE_SESSION_BINDING_MISMATCH")
        require(binding["underlying_debit_id"] == expected_debit, "P2STAR_ROUTE_DEBIT_BINDING_MISMATCH")
        require(binding["scope_id"] == header["scope_id"], "P2STAR_ROUTE_SCOPE_BINDING_MISMATCH")
        require(binding["header_digest"] == header["header_digest"], "P2STAR_ROUTE_HEADER_BINDING_MISMATCH")
        require(binding["session_set_digest"] == header["session_set_digest"], "P2STAR_ROUTE_SESSION_SET_BINDING_MISMATCH")
        require(binding["manifest_digests"] == header["manifest_digests"], "P2STAR_ROUTE_MANIFEST_BINDING_MISMATCH")
        require(int(binding["horizon_end_block"]) == int(captured["finality"]["observed_head_block"]), "P2STAR_ROUTE_HORIZON_BINDING_MISMATCH")
        require(binding["settlement_closed"] is True, "P2STAR_ROUTE_SETTLEMENT_OPEN")
        debit_ids.append(str(binding["underlying_debit_id"]))
        session_ids.append(str(binding["session_id"]))
    require(len(debit_ids) == len(set(debit_ids)), "P2STAR_CROSS_SESSION_DEBIT_REUSE")
    require(len(session_ids) == len(set(session_ids)), "P2STAR_DUPLICATE_SESSION")
def verify_p5_route_inventory(certificate: Mapping[str, Any]) -> None:
    selected_sets = [
        tuple(int(item) for item in route["selected_member_indices"])
        for route in certificate["routes"]
    ]
    require(set(selected_sets) == set(combinations(range(7), 4)) and len(selected_sets) == 35, "P5F_ROUTE_SET_INCOMPLETE")




def verify_attainment(certificate: Mapping[str, Any]) -> None:
    attainment = certificate["attainment"]
    routes = {str(route["route_id"]): route for route in certificate["routes"]}
    require(attainment["route_id"] in routes, "ATTAINMENT_ROUTE_MISSING")
    route = routes[str(attainment["route_id"])]
    require(attainment["session_id"] == route["order_id"], "ATTAINMENT_SESSION_MISMATCH")
    require(attainment["scope_id"] == route["p2star_binding"]["scope_id"], "ATTAINMENT_SCOPE_MISMATCH")
    require(attainment["header_digest"] == route["p2star_binding"]["header_digest"], "ATTAINMENT_HEADER_MISMATCH")
    require(int(attainment["mandatory_outflow_units"]) == int(route["contract_cost_units"]), "ATTAINMENT_OUTFLOW_MISMATCH")
    require(int(attainment["return_units"]) == int(route["process_return_units"]), "ATTAINMENT_RETURN_MISMATCH")
    require(int(attainment["net_cost_units"]) == int(route["net_attacker_cost_units"]) == 4, "ATTAINMENT_COST_MISMATCH")
    require(all(attainment[name] is True for name in ("typed_transfer_recomputed", "settlement_closed", "single_use_verified", "whole_process_replayed")), "ATTAINMENT_OBLIGATION_OPEN")

def schema_ref(document: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    require(reference.startswith("#/"), f"unsupported schema reference: {reference}")
    node: Any = document
    for part in reference[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    require(isinstance(node, Mapping), f"schema reference is not an object: {reference}")
    return node


def validate_schema(value: Any, rule: Mapping[str, Any], document: Mapping[str, Any], path: str = "$") -> None:
    if "$ref" in rule:
        validate_schema(value, schema_ref(document, str(rule["$ref"])), document, path)
        return
    if "const" in rule:
        require(value == rule["const"], f"{path}: constant mismatch")
    if "enum" in rule:
        require(value in rule["enum"], f"{path}: enum mismatch")
    kind = rule.get("type")
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if kind:
        require(kind in checks and checks[kind](value), f"{path}: expected {kind}")
    if isinstance(value, dict):
        required = rule.get("required", [])
        for name in required:
            require(name in value, f"{path}: missing required field {name}")
        properties = rule.get("properties", {})
        additional = rule.get("additionalProperties", True)
        for name, item in value.items():
            if name in properties:
                validate_schema(item, properties[name], document, f"{path}.{name}")
            elif additional is False:
                raise ValueError(f"{path}: unexpected field {name}")
            elif isinstance(additional, Mapping):
                validate_schema(item, additional, document, f"{path}.{name}")
        if "minProperties" in rule:
            require(len(value) >= int(rule["minProperties"]), f"{path}: too few properties")
    if isinstance(value, list):
        if "minItems" in rule:
            require(len(value) >= int(rule["minItems"]), f"{path}: too few items")
        if "maxItems" in rule:
            require(len(value) <= int(rule["maxItems"]), f"{path}: too many items")
        if rule.get("uniqueItems"):
            encoded = [canonical_json_bytes(item) for item in value]
            require(len(encoded) == len(set(encoded)), f"{path}: duplicate items")
        if isinstance(rule.get("items"), Mapping):
            for index, item in enumerate(value):
                validate_schema(item, rule["items"], document, f"{path}[{index}]")
    if isinstance(value, str):
        if "minLength" in rule:
            require(len(value) >= int(rule["minLength"]), f"{path}: string too short")
        if "pattern" in rule:
            require(re.fullmatch(str(rule["pattern"]), value) is not None, f"{path}: pattern mismatch")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in rule:
            require(value >= rule["minimum"], f"{path}: below minimum")
        if "maximum" in rule:
            require(value <= rule["maximum"], f"{path}: above maximum")


def verify_schnorr(public_key: int, message: bytes, signature: Mapping[str, str]) -> bool:
    r = int(signature["r"], 16)
    s = int(signature["s"], 16)
    if not (1 < r < P and 0 <= s < Q and 1 < public_key < P):
        return False
    challenge = hash_to_int(
        Q,
        b"PTR-V3-SCHNORR-CHALLENGE",
        int_to_bytes(r),
        int_to_bytes(public_key),
        message,
    )
    return pow(G, s, P) == r * pow(public_key, challenge, P) % P


def response_signing_message(response: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(
        {
            "protocol_version": response["protocol_version"],
            "operator_id": response["operator_id"],
            "host_id": response["host_id"],
            "order_id": response["order_id"],
            "buyer": response["buyer"],
            "resource": response["resource"],
            "epoch": response["epoch"],
            "partial_hash": response["partial_hash"],
            "proof_hash": response["proof_hash"],
            "nonce": response["nonce"],
            "runtime_source_digest": response["runtime_source_digest"],
        }
    )


def ciphertext_context(ciphertext: Mapping[str, Any]) -> bytes:
    return b"|".join(
        [
            str(ciphertext["buyer"]).encode(),
            str(ciphertext["resource"]).encode(),
            str(ciphertext["order_id"]).encode(),
            int_to_bytes(int(str(ciphertext["c1"]), 16)),
            int_to_bytes(int(str(ciphertext["c2"]), 16)),
            str(ciphertext["plaintext_commitment"]).encode("ascii"),
        ]
    )


def verify_partial(
    operator_id: int,
    public_share: int,
    ciphertext: Mapping[str, Any],
    epoch: int,
    partial: int,
    proof: Mapping[str, str],
) -> bool:
    c1 = int(str(ciphertext["c1"]), 16)
    a1 = int(proof["a1"], 16)
    a2 = int(proof["a2"], 16)
    z = int(proof["z"], 16)
    if not (1 < partial < P and 0 <= z < Q):
        return False
    challenge = hash_to_int(
        Q,
        b"PTR-CP-PROOF-v2",
        operator_id.to_bytes(4, "big"),
        int_to_bytes(G),
        int_to_bytes(public_share),
        int_to_bytes(c1),
        int_to_bytes(partial),
        int_to_bytes(a1),
        int_to_bytes(a2),
        int_to_bytes(epoch),
        ciphertext_context(ciphertext),
    )
    return (
        pow(G, z, P) == a1 * pow(public_share, challenge, P) % P
        and pow(c1, z, P) == a2 * pow(partial, challenge, P) % P
    )


def lagrange_at_zero(index: int, indices: Sequence[int]) -> int:
    numerator = 1
    denominator = 1
    for other in indices:
        if other != index:
            numerator = numerator * (-other) % Q
            denominator = denominator * (index - other) % Q
    return numerator * pow(denominator % Q, -1, Q) % Q


def combine_partials(ciphertext: Mapping[str, Any], responses: Sequence[Mapping[str, Any]]) -> int:
    indices = [int(item["operator_id"]) for item in responses]
    require(len(indices) == 4 and len(set(indices)) == 4, "threshold response set is not 4-of-7")
    combined = 1
    for response in responses:
        operator_id = int(response["operator_id"])
        partial = int(str(response["partial_decryption"]), 16)
        combined = combined * pow(partial, lagrange_at_zero(operator_id, indices), P) % P
    return int(str(ciphertext["c2"]), 16) * pow(combined, -1, P) % P


def verify_plaintext(ciphertext: Mapping[str, Any], plaintext: int) -> bool:
    commitment = sha256_hex(
        b"|".join(
            [
                b"PTR-PLAINTEXT-COMMITMENT-v5",
                str(ciphertext["buyer"]).encode(),
                str(ciphertext["resource"]).encode(),
                str(ciphertext["order_id"]).encode(),
                int_to_bytes(plaintext),
            ]
        )
    )
    return commitment == ciphertext["plaintext_commitment"]


def verify_eip191_capture() -> None:
    node = shutil.which("node")
    require(node is not None, "Node.js is required to independently verify EIP-191 requests")
    completed = subprocess.run(
        [node, str(AUTH_VERIFIER), str(ROUTES_PATH)],
        cwd=AUTH_VERIFIER.parent.parent,
        check=False,
        capture_output=True,
        text=True,
    )
    require(completed.returncode == 0, f"EIP-191 verifier failed: {completed.stderr}")
    require("OPE_BUYER_AUTH_ROUTES=35_OF_35" in completed.stdout, "EIP-191 route coverage missing")


def verify_source_inventory(certificate: Mapping[str, Any]) -> None:
    inventory = certificate["runtime"]["source_inventory"]
    for relative, digest in inventory["module_sha256"].items():
        require(file_sha256(HERE / relative) == digest, f"runtime source hash mismatch: {relative}")
    require(file_sha256(RUNNER_PATH) == inventory["runner_sha256"], "generator source hash mismatch")
    require(file_sha256(SCHEMA_PATH) == inventory["certificate_schema_sha256"], "schema hash mismatch")
    require(file_sha256(Path(__file__).resolve()) == inventory["independent_verifier_sha256"], "independent verifier hash mismatch")
    require(inventory["served_http_routes"] == ["POST /respond", "GET /health"], "runtime route surface mismatch")
    require(inventory["economic_transfer_api_present"] is False, "undeclared service economic API")


def capture_costs(capture: Mapping[str, Any], attacker: str) -> dict[tuple[int, ...], tuple[int, Mapping[str, Any]]]:
    require(capture["schema"] == "ope-controlled-process-routes/v1", "capture schema mismatch")
    require(capture["scope"]["configuration_credits_units"] == FIXED_CREDITS, "fixed credit root mismatch")
    require(capture["scope"]["first_success_ends_at_commitment_valid_plaintext_delivery"] is True, "success boundary mismatch")
    require(str(capture["roles"]["attacker"]).lower() == attacker, "capture attacker mismatch")
    controller = str(capture["roles"]["service_contract_controller"]).lower()
    members = [str(item).lower() for item in capture["roles"]["committee_member_addresses"]]
    require(len(set(members)) == 7 and attacker not in members and controller not in members and attacker != controller, "role separation mismatch")
    output: dict[tuple[int, ...], tuple[int, Mapping[str, Any]]] = {}
    for route in capture["routes"]:
        selected = tuple(int(item) for item in route["selected_member_indices"])
        require(selected == tuple(sorted(set(selected))) and len(selected) == 4, "capture terminal set mismatch")
        require(route["selected_operator_ids"] == [item + 1 for item in selected], "capture operator mapping mismatch")
        payment = route["payment_transaction"]
        terminal = route["terminal_state"]
        finality = route["finality"]
        authentication = route["request_authentication"]
        require(payment["status"] == "success" and str(payment["from"]).lower() == attacker, "capture payment origin mismatch")
        require(str(payment["to"]).lower() == str(route["contract"]["address"]).lower(), "capture payment destination mismatch")
        require(int(finality["policy_confirmations"]) == 6 and int(finality["observed_confirmations"]) >= 6, "capture finality mismatch")
        require(authentication["scheme"] == "EIP-191/secp256k1" and str(authentication["recovered_signer"]).lower() == attacker, "capture request authentication mismatch")
        require(terminal["completed"] is True and str(terminal["acquirer"]).lower() == attacker, "capture success mismatch")
        require(int(terminal["buyer_claimable_wei"]) == 0, "capture buyer return remains open")
        require(int(terminal["total_acquisition_call_value_wei"]) == int(payment["value_wei"]), "capture debit mismatch")
        require(all(bool(value) for value in route["single_use"].values()), "capture single-use check failed")
        value = int(payment["value_wei"])
        require(value % UNIT_WEI == 0, "capture cost is not an integral accounting unit")
        require(selected not in output, "duplicate capture terminal set")
        output[selected] = (value // UNIT_WEI, route)
    require(set(output) == set(combinations(range(7), 4)), "capture does not cover every terminal choice")
    return output


def verify_c6(c6_document: Mapping[str, Any], costs: Mapping[tuple[int, ...], tuple[int, Mapping[str, Any]]], binding: Mapping[str, Any]) -> None:
    require(c6_document["schema"] == binding["source_schema"], "C6 document schema mismatch")
    c6 = c6_document["c6"]
    require(c6["status"] == "PASS", "C6 is not PASS")
    records = [item for item in c6["records"] if item["credit_vector"] == FIXED_CREDITS]
    require(len(records) == 35, "C6 fixed root is incomplete")
    seen: set[tuple[int, ...]] = set()
    for record in records:
        selected = tuple(int(item) for item in record["canonical_action"]["arguments"])
        require(selected in costs, "C6 route absent from executable capture")
        require(int(record["local_cost_units"]) == costs[selected][0], "C6 cost is not preserved")
        require(record["reverse_proof_bounds"] == [], "C6 reverse replay is bounded")
        require(int(record["reverse_proof_paths"]) > 0, "C6 reverse witness missing")
        seen.add(selected)
    require(seen == set(costs), "C6 fixed-root route set mismatch")
    require(c6["records_sha256"] == binding["source_records_sha256"], "C6 record digest mismatch")
    require(int(c6["forward_success_paths"]) == int(binding["full_contract_forward_routes"]) == 4095, "C6 forward count mismatch")
    require(int(c6["reverse_realized_paths"]) == int(binding["full_contract_reverse_routes"]) == 4095, "C6 reverse count mismatch")


def verify_bindings(certificate: Mapping[str, Any], capture: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    committee = certificate["runtime"]["committee"]
    hosts = {int(key): str(value) for key, value in committee["operator_hosts"].items()}
    network_keys = {int(key): int(str(value), 16) for key, value in committee["network_public_keys"].items()}
    registry = [
        {"operator_id": operator_id, "host_id": hosts[operator_id], "network_public_key": hex(network_keys[operator_id])}
        for operator_id in sorted(hosts)
    ]
    registry_digest = sha256_hex(canonical_json_bytes(registry))
    members = [str(item).lower() for item in capture["roles"]["committee_member_addresses"]]
    runtime_hashes = {str(route["contract"]["runtime_bytecode_keccak256"]).lower() for route in capture["routes"]}
    require(len(runtime_hashes) == 1, "capture runtime bytecode is not fixed")
    runtime_hash = next(iter(runtime_hashes))
    output: dict[int, Mapping[str, Any]] = {}
    for binding in certificate["runtime"]["signed_bindings"]:
        operator_id = int(binding["operator_id"])
        statement = {key: value for key, value in binding.items() if key != "signature"}
        require(operator_id == int(binding["member_index"]) + 1, "binding member/operator index mismatch")
        require(str(binding["member_address"]).lower() == members[operator_id - 1], "binding member mismatch")
        require(binding["host_id"] == hosts[operator_id], "binding host mismatch")
        require(int(binding["network_public_key"], 16) == network_keys[operator_id], "binding network key mismatch")
        require(binding["operator_registry_digest"] == registry_digest, "binding registry digest mismatch")
        require(str(binding["ope_runtime_bytecode_keccak256"]).lower() == runtime_hash, "binding runtime mismatch")
        require(verify_schnorr(network_keys[operator_id], canonical_json_bytes(statement), binding["signature"]), "binding signature rejected")
        require(operator_id not in output, "duplicate signed binding")
        output[operator_id] = binding
    require(set(output) == set(range(1, 8)), "signed binding set incomplete")
    return output


def verify_route_crypto(route: Mapping[str, Any], committee: Mapping[str, Any], attacker: str) -> tuple[int, int]:
    public_shares = {int(key): int(str(value), 16) for key, value in committee["public_shares"].items()}
    network_keys = {int(key): int(str(value), 16) for key, value in committee["network_public_keys"].items()}
    hosts = {int(key): str(value) for key, value in committee["operator_hosts"].items()}
    ciphertext = route["ciphertext"]
    require(str(ciphertext["buyer"]).lower() == attacker, "ciphertext buyer mismatch")
    require(ciphertext["order_id"] == route["order_id"], "ciphertext order mismatch")
    responses = route["operator_responses"]
    require([int(item["operator_id"]) for item in responses] == route["selected_operator_ids"], "response/operator order mismatch")
    runtime_digest = str(route["operator_responses"][0]["runtime_source_digest"])
    for response in responses:
        operator_id = int(response["operator_id"])
        proof = response["chaum_pedersen_proof"]
        partial = int(str(response["partial_decryption"]), 16)
        normalized_proof = {name: hex(int(str(proof[name]), 16)) for name in ("a1", "a2", "z")}
        require(response["partial_hash"] == sha256_hex(canonical_json_bytes({"value": hex(partial)})), "partial digest mismatch")
        require(response["proof_hash"] == sha256_hex(canonical_json_bytes(normalized_proof)), "proof digest mismatch")
        require(response["host_id"] == hosts[operator_id], "response host mismatch")
        require(str(response["buyer"]).lower() == attacker, "response buyer mismatch")
        require(response["order_id"] == route["order_id"] and response["resource"] == ciphertext["resource"], "response session mismatch")
        require(response["runtime_source_digest"] == runtime_digest, "response runtime digest mismatch")
        require(verify_schnorr(network_keys[operator_id], response_signing_message(response), response["operator_signature"]), "operator response signature rejected")
        require(verify_partial(operator_id, public_shares[operator_id], ciphertext, int(response["epoch"]), partial, normalized_proof), "Chaum-Pedersen proof rejected")
    plaintext = combine_partials(ciphertext, responses)
    require(verify_plaintext(ciphertext, plaintext), "plaintext commitment rejected")
    delivery = route["delivery"]
    require(delivery["plaintext_commitment_verified"] is True, "delivery commitment flag missing")
    require(str(delivery["recipient"]).lower() == attacker and int(delivery["response_count"]) == 4, "delivery recipient/threshold mismatch")
    require(delivery["plaintext_sha256"] == sha256_hex(int_to_bytes(plaintext)), "delivered plaintext digest mismatch")
    return len(responses), len(responses)


def verify_certificate(
    certificate_path: Path = CERTIFICATE_PATH,
    *,
    route_limit: int | None = None,
    verify_eip191: bool = True,
) -> dict[str, int | float]:
    started = time.perf_counter()
    certificate = read_json(certificate_path)
    schema = read_json(SCHEMA_PATH)
    validate_schema(certificate, schema, schema)
    require(certificate["verdict"] == EXPECTED_VERDICT, "verdict mismatch")
    require(certificate["claim"]["claim_type"] == "boundary-complete-authenticated-relative-process-cost", "claim is not explicitly P2-star boundary-complete")
    attacker = str(certificate["claim"]["attacker_role"]).lower()
    model = certificate["model"]
    require(model["control_boundary"]["attacker"] == attacker, "control-boundary attacker mismatch")
    require(model["control_boundary"]["included_identities"] == [attacker], "control closure changed")
    require(all(model["p5_completeness"].values()), "P5 completeness condition is open")
    require(all(certificate["p1_p5"][gate]["status"] == "PASS" for gate in ("P1", "P2_star", "P3", "P4", "P5")), "P1/P2-star/P3/P4/P5 not all PASS")
    require(file_sha256(ROUTES_PATH) == certificate["inputs"]["ope_routes_sha256"], "OPE capture hash mismatch")
    require(file_sha256(C6_PATH) == certificate["inputs"]["c6_certificate_sha256"], "C6 certificate hash mismatch")
    require(file_sha256(REFINEMENT_PATH) == certificate["inputs"]["refinement_certificate_sha256"], "refinement certificate hash mismatch")
    require(file_sha256(CONTRACT_SOURCE_PATH) == certificate["inputs"]["contract_source_sha256"], "contract source hash mismatch")
    verify_source_inventory(certificate)
    capture = read_json(ROUTES_PATH)
    c6_document = read_json(C6_PATH)
    refinement = read_json(REFINEMENT_PATH)
    verify_p2star_boundary(certificate, capture, refinement)
    verify_p2star_route_bindings(certificate, capture)
    if verify_eip191:
        verify_eip191_capture()
    costs = capture_costs(capture, attacker)
    verify_c6(c6_document, costs, certificate["route_coverage"]["contract_certificate_binding"])
    verify_bindings(certificate, capture)
    verify_p5_route_inventory(certificate)

    routes = certificate["routes"]
    route_ids: set[str] = set()
    net_costs: list[int] = []
    returns = 0
    for route in routes:
        selected = tuple(int(item) for item in route["selected_member_indices"])
        expected_cost, capture_route = costs[selected]
        require(route["selected_operator_ids"] == [item + 1 for item in selected], "certificate operator mapping mismatch")
        require(route["route_id"] == capture_route["route_id"] and route["payment_tx_hash"] == capture_route["payment_transaction"]["hash"], "certificate/capture route binding mismatch")
        require(route["order_id"] == f"ope-process:{route['payment_tx_hash'].lower()}", "process order binding mismatch")
        require(int(route["contract_cost_units"]) == expected_cost, "route contract cost mismatch")
        require(int(route["contract_cost_units"]) - int(route["process_return_units"]) == int(route["net_attacker_cost_units"]), "route net-cost equation mismatch")
        require(all(route[name] is True for name in (
            "p1_authenticated_request_and_delivery",
            "p2star_boundary_and_session_binding",
            "p3_finality_policy_satisfied",
            "p4_returns_complete_and_debit_single_use",
            "p5_complete_route_replayed",
        )), "route gate flag is open")
        require(route["route_id"] not in route_ids, "duplicate route id")
        route_ids.add(route["route_id"])
        net_costs.append(int(route["net_attacker_cost_units"]))
        returns += int(route["process_return_units"])

    limit = len(routes) if route_limit is None else int(route_limit)
    require(1 <= limit <= len(routes), "route benchmark limit out of range")
    signatures = 0
    proofs = 0
    for route in routes[:limit]:
        route_signatures, route_proofs = verify_route_crypto(route, certificate["runtime"]["committee"], attacker)
        signatures += route_signatures
        proofs += route_proofs

    cost = certificate["cost"]
    require(min(net_costs) == int(cost["process_minimum_units"]) == 4, "process minimum mismatch")
    require(max(net_costs) == int(cost["process_maximum_units"]), "process maximum mismatch")
    require(min(item[0] for item in costs.values()) == int(cost["contract_minimum_units"]) == 4, "contract minimum mismatch")
    require(returns == int(cost["all_returns_to_attacker_units"]) == 0, "return accounting mismatch")
    require(certificate["return_interface"]["buyer_claimable_after_success_wei"] == 0, "buyer claimable balance open")
    require(certificate["return_interface"]["buyer_withdraw_rejected_on_all_routes"] is True, "buyer withdrawal route open")
    require(certificate["return_interface"]["refund_cancel_rebate_entry_points"] == [], "refund/rebate route open")
    require(certificate["return_interface"]["service_runtime_economic_transfer_apis"] == [], "service transfer API open")
    require(certificate["return_interface"]["cross_session_return_entry_points"] == [], "cross-session return open")
    require(len(certificate["mutations"]["executable"]) == 4 and all(certificate["mutations"]["executable"].values()), "executable mutation rejection incomplete")
    verify_attainment(certificate)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "certificate_bytes": certificate_path.stat().st_size,
        "declared_routes": len(routes),
        "cryptographically_verified_routes": limit,
        "operator_signatures_verified": signatures,
        "chaum_pedersen_proofs_verified": proofs,
        "elapsed_ms": elapsed_ms,
    }



def rebind_mutated_certificate(candidate: dict[str, Any]) -> None:
    header = candidate["boundary"]["header"]
    manifests = candidate["boundary"]["manifests"]
    manifest_digests = {
        name: json_digest(envelope["body"]) for name, envelope in manifests.items()
    }
    header["manifest_digests"] = manifest_digests
    header_core = {name: value for name, value in header.items() if name != "header_digest"}
    header_digest = json_digest(header_core)
    header["header_digest"] = header_digest
    for name, envelope in manifests.items():
        envelope["body_digest"] = manifest_digests[name]
        envelope["scope_id"] = header["scope_id"]
        envelope["header_digest"] = header_digest
        envelope["session_set_digest"] = header["session_set_digest"]
    for route in candidate["routes"]:
        binding = route["p2star_binding"]
        binding["scope_id"] = header["scope_id"]
        binding["header_digest"] = header_digest
        binding["session_set_digest"] = header["session_set_digest"]
        binding["manifest_digests"] = manifest_digests
    candidate["attainment"]["scope_id"] = header["scope_id"]
    candidate["attainment"]["header_digest"] = header_digest


def run_p2star_mutations(certificate: Mapping[str, Any]) -> dict[str, Any]:
    capture = read_json(ROUTES_PATH)
    refinement = read_json(REFINEMENT_PATH)

    def delete_control_account(candidate: dict[str, Any]) -> None:
        candidate["boundary"]["manifests"]["control"]["body"]["attacker_control_accounts"] = []
        rebind_mutated_certificate(candidate)

    def hide_return_interface(candidate: dict[str, Any]) -> None:
        body = candidate["boundary"]["manifests"]["settlement_surface"]["body"]
        body["value_transfer_entry_points"] = []
        body["attacker_return_interfaces"] = []
        rebind_mutated_certificate(candidate)

    def hide_funding_path(candidate: dict[str, Any]) -> None:
        body = candidate["boundary"]["manifests"]["acquisition_links"]["body"]
        body["funding_paths"] = [
            path for path in body["funding_paths"]
            if path["path_id"] != "attacker-acquisition-payment"
        ]
        rebind_mutated_certificate(candidate)

    def add_cross_session_reuse(candidate: dict[str, Any]) -> None:
        candidate["routes"][1]["p2star_binding"]["underlying_debit_id"] = (
            candidate["routes"][0]["p2star_binding"]["underlying_debit_id"]
        )

    def splice_sessions(candidate: dict[str, Any]) -> None:
        candidate["routes"][1]["p2star_binding"]["session_id"] = (
            candidate["routes"][0]["p2star_binding"]["session_id"]
        )

    def change_horizon(candidate: dict[str, Any]) -> None:
        body = candidate["boundary"]["manifests"]["horizon"]["body"]
        body["end_condition"] = "first delivery only"
        rebind_mutated_certificate(candidate)

    def delete_successful_route(candidate: dict[str, Any]) -> None:
        candidate["routes"].pop()

    def change_attainment_cost(candidate: dict[str, Any]) -> None:
        candidate["attainment"]["net_cost_units"] = (
            int(candidate["attainment"]["net_cost_units"]) + 1
        )

    mutations = {
        "delete_control_account": (delete_control_account, "BOUNDARY-UNKNOWN", "P2STAR_CONTROL_MANIFEST_MISMATCH"),
        "hide_attacker_funding_path": (hide_funding_path, "BOUNDARY-UNKNOWN", "P2STAR_ACQUISITION_LINK_MANIFEST_MISMATCH"),
        "hide_return_interface": (hide_return_interface, "BOUNDARY-UNKNOWN", "P2STAR_SETTLEMENT_SURFACE_MISMATCH"),
        "add_cross_session_reuse": (add_cross_session_reuse, "BOUNDARY-UNKNOWN", "P2STAR_ROUTE_DEBIT_BINDING_MISMATCH"),
        "splice_two_sessions": (splice_sessions, "BOUNDARY-UNKNOWN", "P2STAR_ROUTE_SESSION_BINDING_MISMATCH"),
        "change_settlement_horizon": (change_horizon, "BOUNDARY-UNKNOWN", "P2STAR_HORIZON_MANIFEST_MISMATCH"),
        "delete_successful_route": (delete_successful_route, "EXACTNESS-NOT-ESTABLISHED", "P5F_ROUTE_SET_INCOMPLETE"),
        "change_attainment_cost": (change_attainment_cost, "LOWER-BOUND-CERTIFIED(4)", "ATTAINMENT_COST_MISMATCH"),
    }
    results: dict[str, Any] = {}
    for name, (transform, expected_verdict, expected_reason) in mutations.items():
        candidate = deepcopy(certificate)
        transform(candidate)
        observed_reason = "ACCEPTED"
        try:
            verify_p2star_boundary(candidate, capture, refinement)
            verify_p2star_route_bindings(candidate, capture)
            verify_p5_route_inventory(candidate)
            verify_attainment(candidate)
        except ValueError as error:
            observed_reason = str(error).split(":", 1)[0]
        if observed_reason == "ACCEPTED":
            observed_verdict = EXPECTED_VERDICT
        elif observed_reason.startswith("ATTAINMENT_"):
            observed_verdict = "LOWER-BOUND-CERTIFIED(4)"
        elif observed_reason.startswith("P5"):
            observed_verdict = "EXACTNESS-NOT-ESTABLISHED"
        else:
            observed_verdict = "BOUNDARY-UNKNOWN"
        results[name] = {
            "expected_verdict": expected_verdict,
            "observed_verdict": observed_verdict,
            "expected_reason": expected_reason,
            "observed_reason": observed_reason,
            "rejected": observed_reason == expected_reason and observed_verdict == expected_verdict,
        }
    require(all(item["rejected"] for item in results.values()), "P2STAR_MUTATION_SUITE_FAILED")
    return {
        "schema": "ope-p2star-mutation-results/v1",
        "certificate_sha256": file_sha256(CERTIFICATE_PATH),
        "checker_sha256": file_sha256(Path(__file__).resolve()),
        "positive_verdict": EXPECTED_VERDICT,
        "mutation_count": len(results),
        "all_rejected": True,
        "results": results,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificate", type=Path, default=CERTIFICATE_PATH)
    parser.add_argument("--route-limit", type=int)
    parser.add_argument("--skip-eip191", action="store_true")
    parser.add_argument("--write-mutations", action="store_true")
    parser.add_argument("--verify-mutations", action="store_true")
    args = parser.parse_args()
    metrics = verify_certificate(
        args.certificate.resolve(),
        route_limit=args.route_limit,
        verify_eip191=not args.skip_eip191,
    )
    print("OPE_PROCESS_SCHEMA=PASS")
    print("OPE_PROCESS_P2STAR_BOUNDARY=PASS")
    print("OPE_PROCESS_ATTAINMENT=PASS")
    print("OPE_PROCESS_INPUT_BINDINGS=PASS")
    print(f"OPE_PROCESS_CRYPTO_ROUTES={metrics['cryptographically_verified_routes']}_OF_{metrics['declared_routes']}")
    print(f"OPE_PROCESS_CERTIFICATE_BYTES={metrics['certificate_bytes']}")
    print(f"OPE_PROCESS_VERIFY_MS={metrics['elapsed_ms']:.3f}")
    if metrics["cryptographically_verified_routes"] == metrics["declared_routes"]:
        print(EXPECTED_VERDICT)
        print("INDEPENDENT_OPE_PROCESS_VERIFIER=PASS")
    else:
        print("SCALING_PROBE_ONLY=PASS")
    mutation_results = run_p2star_mutations(read_json(args.certificate.resolve()))
    if args.write_mutations:
        write_json(MUTATION_RESULTS_PATH, mutation_results)
    else:
        require(MUTATION_RESULTS_PATH.exists(), "P2STAR_MUTATION_RESULTS_MISSING")
        require(read_json(MUTATION_RESULTS_PATH) == mutation_results, "P2STAR_MUTATION_RESULTS_DRIFT")
    if args.verify_mutations or args.write_mutations:
        print(f"OPE_PROCESS_P2STAR_MUTATIONS={mutation_results['mutation_count']}_OF_{mutation_results['mutation_count']}")
        for name, result in mutation_results["results"].items():
            print(f"P2STAR_MUTATION_{name.upper()}={result['observed_verdict']}:{result['observed_reason']}")


if __name__ == "__main__":
    main()
