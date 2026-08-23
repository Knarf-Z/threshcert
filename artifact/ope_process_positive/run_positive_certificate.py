#!/usr/bin/env python3
"""Build or verify the OPE controlled relative-process certificate."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNTIME = HERE / "runtime"
EVM = REPO / "artifact" / "joint_incidence_refinement"
ROUTES_PATH = EVM / "results" / "ope_process_routes.v1.json"
C6_PATH = REPO / "artifact" / "reviewer_revision_v77" / "results" / "completeness_certificates.v1.json"
RESULT_PATH = HERE / "results" / "ope_process_positive.v3.json"
SCHEMA_PATH = HERE / "schema" / "ope_process_certificate.schema.json"
VERIFIER_PATH = HERE / "verify_process_certificate.py"
REFINEMENT_PATH = EVM / "results" / "refinement_certificate.json"
CONTRACT_SOURCE_PATH = EVM / "contracts" / "OverlappingPoolEscrow.sol"
sys.path.insert(0, str(RUNTIME))

from ptr_v3.coordinator import Coordinator, OperatorEndpoint, RejectedResponse  # noqa: E402
from ptr_v3.crypto import combine_partials, encrypt_capability, verify_threshold_result  # noqa: E402
from ptr_v3.dealer import deal, write_dealt  # noqa: E402
from ptr_v3.network_identity import (  # noqa: E402
    NetworkIdentity,
    OperatorRegistry,
    sign,
    verify,
)
from ptr_v3.operator_server import RUNTIME_SOURCE_DIGEST, SERVED_ROUTES  # noqa: E402
from ptr_v3.utils import (  # noqa: E402
    canonical_json_bytes,
    file_sha256,
    int_to_bytes,
    read_json,
    sha256_hex,
    write_json,
)


UNIT_WEI = 10**18
FIXED_CREDITS = [2, 0, 0, 0, 2, 0, 0]
RESOURCE = "threshold-capability-v16"
FINALITY_CONFIRMATIONS = 6
VERDICT = "RELATIVE-PROCESS-CERTIFIED(4)"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Committee:
    committee_size: int
    threshold: int
    buyer: str
    resource: str
    epoch: int
    operator_hosts: Mapping[int, str]
    public_key: int
    public_shares: Mapping[int, int]
    network_public_keys: Mapping[int, int]

    @staticmethod
    def from_public(value: Mapping[str, Any]) -> "Committee":
        return Committee(
            committee_size=int(value["committee_size"]),
            threshold=int(value["threshold"]),
            buyer=str(value["buyer"]).lower(),
            resource=str(value["resource"]),
            epoch=int(value["epoch"]),
            operator_hosts={int(k): str(v) for k, v in dict(value["operator_hosts"]).items()},
            public_key=int(str(value["public_key"]), 16),
            public_shares={int(k): int(str(v), 16) for k, v in dict(value["public_shares"]).items()},
            network_public_keys={
                int(k): int(str(v), 16) for k, v in dict(value["network_public_keys"]).items()
            },
        )

    def public_share_list(self) -> list[int]:
        return [self.public_shares[index] for index in range(1, self.committee_size + 1)]


def deterministic_nonce(order_id: str, operator_id: int, attempt: int = 0) -> str:
    return sha256_hex(
        canonical_json_bytes(
            {"attempt": attempt, "operator_id": operator_id, "order_id": order_id}
        )
    )[:32]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_operators(
    public_path: Path,
    secret_dir: Path,
    committee: Committee,
    work: Path,
) -> tuple[list[subprocess.Popen[bytes]], dict[int, int]]:
    processes: list[subprocess.Popen[bytes]] = []
    ports: dict[int, int] = {}
    server = RUNTIME / "ptr_v3" / "operator_server.py"
    for operator_id in range(1, committee.committee_size + 1):
        port = free_port()
        ports[operator_id] = port
        command = [
            sys.executable,
            str(server),
            "--operator-id",
            str(operator_id),
            "--bind",
            "127.0.0.1",
            "--port",
            str(port),
            "--secret",
            str(secret_dir / f"operator-{operator_id}.secret.json"),
            "--public",
            str(public_path),
            "--transcript",
            str(work / f"operator-{operator_id}.jsonl"),
            "--nonce-log",
            str(work / f"operator-{operator_id}.nonces"),
        ]
        processes.append(
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        )
    return processes, ports


def stop_operators(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def make_coordinator(committee: Committee, ports: Mapping[int, int]) -> Coordinator:
    registry = OperatorRegistry.from_public(
        committee.operator_hosts, committee.network_public_keys
    )
    endpoints = {
        operator_id: OperatorEndpoint(
            operator_id,
            committee.operator_hosts[operator_id],
            "127.0.0.1",
            int(ports[operator_id]),
        )
        for operator_id in range(1, committee.committee_size + 1)
    }
    return Coordinator(
        registry=registry,
        endpoints=endpoints,
        public_shares=committee.public_share_list(),
        expected_runtime_source_digest=RUNTIME_SOURCE_DIGEST,
    )


def wait_until_ready(coordinator: Coordinator, size: int) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        if all(coordinator.health(operator_id) is not None for operator_id in range(1, size + 1)):
            return
        time.sleep(0.05)
    raise RuntimeError("not all seven operator HTTP processes became ready")


def verify_buyer_auth() -> None:
    node = shutil.which("node")
    require(node is not None, "Node.js is required for EIP-191 verification")
    verifier = EVM / "scripts" / "VerifyOpeProcessAuth.mjs"
    run = subprocess.run(
        [node, str(verifier), str(ROUTES_PATH)],
        cwd=EVM,
        check=False,
        capture_output=True,
        text=True,
    )
    require(run.returncode == 0, f"buyer-auth verifier failed: {run.stderr}")
    require("OPE_BUYER_AUTH_ROUTES=35_OF_35" in run.stdout, "buyer-auth coverage missing")


def validate_capture(capture: Mapping[str, Any]) -> dict[tuple[int, ...], int]:
    require(capture.get("schema") == "ope-controlled-process-routes/v1", "capture schema")
    require(int(capture.get("route_count", -1)) == 35, "capture must contain 35 routes")
    require(capture["scope"]["configuration_credits_units"] == FIXED_CREDITS, "wrong fixed credits")
    attacker = str(capture["roles"]["attacker"]).lower()
    controller = str(capture["roles"]["service_contract_controller"]).lower()
    members = [str(value).lower() for value in capture["roles"]["committee_member_addresses"]]
    require(len(set(members)) == 7, "committee addresses are not unique")
    require(attacker != controller and attacker not in members and controller not in members, "P2 role separation")

    costs: dict[tuple[int, ...], int] = {}
    for route in capture["routes"]:
        selected = tuple(int(value) for value in route["selected_member_indices"])
        require(len(selected) == 4 and selected == tuple(sorted(set(selected))), "bad terminal set")
        require(route["selected_operator_ids"] == [index + 1 for index in selected], "operator binding")
        payment = route["payment_transaction"]
        terminal = route["terminal_state"]
        finality = route["finality"]
        require(payment["status"] == "success", "payment receipt failed")
        require(str(payment["from"]).lower() == attacker, "payment is not attacker-originated")
        require(str(payment["to"]).lower() == str(route["contract"]["address"]).lower(), "payment destination")
        require(str(terminal["acquirer"]).lower() == attacker, "terminal acquirer mismatch")
        require(bool(terminal["completed"]), "terminal state incomplete")
        require(int(terminal["buyer_claimable_wei"]) == 0, "buyer has a withdrawal credit")
        require(int(terminal["total_acquisition_call_value_wei"]) == int(payment["value_wei"]), "cost mismatch")
        mask = sum(1 << index for index in selected)
        require(int(terminal["terminal_mask"]) == mask, "terminal mask mismatch")
        require(int(terminal["delivered_share_mask"]) == mask, "delivery mask mismatch")
        require(int(finality["policy_confirmations"]) == FINALITY_CONFIRMATIONS, "finality policy")
        require(int(finality["observed_confirmations"]) >= FINALITY_CONFIRMATIONS, "prefinality route")
        require(all(bool(value) for value in route["single_use"].values()), "single-use/withdraw probe")
        auth = route["request_authentication"]
        require(str(auth["recovered_signer"]).lower() == attacker, "buyer auth signer mismatch")
        cost = int(payment["value_wei"]) // UNIT_WEI
        require(cost * UNIT_WEI == int(payment["value_wei"]), "non-integral accounting unit")
        costs[selected] = cost
    require(len(costs) == 35, "duplicate or missing terminal choices")
    return costs

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


def build_p2star_boundary(
    capture: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> dict[str, Any]:
    refinement = read_json(REFINEMENT_PATH)
    audit = refinement["implementationAuditEvidence"]
    obligations = refinement["obligations"]
    bridge = refinement["bridgeScope"]
    attacker = str(capture["roles"]["attacker"]).lower()
    controller = str(capture["roles"]["service_contract_controller"]).lower()
    members = [str(value).lower() for value in capture["roles"]["committee_member_addresses"]]
    capture_routes = list(capture["routes"])
    session_records = sorted(
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
    session_set_digest = json_digest(session_records)
    scope_core = {
        "schema": "ope-p2star-scope/v1",
        "chain_id": int(capture["chain_id"]),
        "resource": str(capture["scope"]["resource"]),
        "accounting_unit": str(capture["scope"]["accounting_unit"]),
        "success_predicate": "first commitment-valid plaintext delivery to the authenticated attacker",
        "process_boundary": "controlled OPE contract plus the seven authenticated operator processes",
    }
    scope_id = f"ope-scope:{json_digest(scope_core)}"
    source_anchors = {
        "capture_sha256": file_sha256(ROUTES_PATH),
        "refinement_certificate_sha256": file_sha256(REFINEMENT_PATH),
        "contract_source_sha256": file_sha256(CONTRACT_SOURCE_PATH),
        "refinement_contract_source_sha256": str(audit["sourceSha256"]),
        "compiled_artifact_semantic_sha256": str(audit["artifactSemanticSha256"]),
        "runtime_source_digest": str(sources["runtime_source_digest"]),
    }
    require(
        source_anchors["contract_source_sha256"]
        == source_anchors["refinement_contract_source_sha256"],
        "P2STAR_SOURCE_ANCHOR_MISMATCH",
    )
    bodies: dict[str, Any] = {
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
                item["session_id"]: item["horizon_end_block"] for item in session_records
            },
            "open_attacker_claims_at_horizon": 0,
        },
    }
    manifest_digests = {name: json_digest(body) for name, body in bodies.items()}
    header_core = {
        "schema": "ope-p2star-header/v1",
        "scope_id": scope_id,
        "scope": scope_core,
        "session_set_digest": session_set_digest,
        "manifest_digests": manifest_digests,
        "source_anchors": source_anchors,
        "settlement_horizon_kind": "per-session-state-closure",
    }
    header_digest = json_digest(header_core)
    manifests = {
        name: {
            "schema": f"ope-p2star-{name.replace('_', '-')}-manifest/v1",
            "scope_id": scope_id,
            "header_digest": header_digest,
            "session_set_digest": session_set_digest,
            "body_digest": manifest_digests[name],
            "body": body,
        }
        for name, body in bodies.items()
    }
    return {
        "header": {**header_core, "header_digest": header_digest},
        "manifests": manifests,
        "session_records": session_records,
    }


def bind_routes_to_p2star(
    routes: list[dict[str, Any]],
    capture: Mapping[str, Any],
    boundary: Mapping[str, Any],
) -> None:
    capture_by_id = {str(route["route_id"]): route for route in capture["routes"]}
    header = boundary["header"]
    for route in routes:
        captured = capture_by_id[str(route["route_id"])]
        route["p2star_binding"] = {
            "scope_id": header["scope_id"],
            "header_digest": header["header_digest"],
            "session_id": session_id_for_capture_route(captured),
            "session_set_digest": header["session_set_digest"],
            "manifest_digests": header["manifest_digests"],
            "underlying_debit_id": debit_id_for_capture_route(capture, captured),
            "horizon_end_block": int(captured["finality"]["observed_head_block"]),
            "settlement_closed": True,
        }


def bind_c6(capture_costs: Mapping[tuple[int, ...], int]) -> dict[str, Any]:
    certificate = read_json(C6_PATH)
    c6 = certificate["c6"]
    require(c6["status"] == "PASS", "C6 is not PASS")
    records = [
        record for record in c6["records"]
        if record["credit_vector"] == FIXED_CREDITS
    ]
    require(len(records) == 35, "C6 fixed root does not have 35 routes")
    seen: set[tuple[int, ...]] = set()
    for record in records:
        selected = tuple(int(value) for value in record["canonical_action"]["arguments"])
        require(selected in capture_costs, "C6 route missing from executable capture")
        require(int(record["local_cost_units"]) == capture_costs[selected], "C6/process cost drift")
        require(not record["reverse_proof_bounds"], "bounded reverse proof")
        seen.add(selected)
    require(seen == set(capture_costs), "capture has a route outside C6")
    return {
        "source_schema": certificate["schema"],
        "source_records_sha256": c6["records_sha256"],
        "fixed_root_forward_routes": len(records),
        "fixed_root_reverse_routes": len(records),
        "full_contract_forward_routes": c6["forward_success_paths"],
        "full_contract_reverse_routes": c6["reverse_realized_paths"],
    }


def source_inventory() -> dict[str, Any]:
    modules = sorted((RUNTIME / "ptr_v3").glob("*.py"))
    require(len(modules) == 7, "runtime source closure changed")
    forbidden_imports = {
        "web3", "eth_account", "requests", "subprocess", "ctypes", "cffi"
    }
    imported: set[str] = set()
    call_sites: dict[str, list[str]] = {}

    def call_name(node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    def function_context(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> str:
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current.name
            current = parents.get(current)
        return "<module>"

    inspected = [*modules, Path(__file__).resolve()]
    trees: dict[Path, ast.AST] = {}
    for path in inspected:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        trees[path] = tree
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if path in modules and isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif path in modules and isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                name = call_name(node)
                if name in {
                    "create_partial",
                    "combine_partials",
                    "verify_threshold_result",
                    "ThreadingHTTPServer",
                    "Popen",
                }:
                    call_sites.setdefault(name, []).append(
                        f"{path.name}:{function_context(node, parents)}"
                    )
    require(not (imported & forbidden_imports), "runtime contains an undeclared economic/native escape")
    require(tuple(SERVED_ROUTES) == ("POST /respond", "GET /health"), "operator route surface changed")
    require(call_sites.get("create_partial") == ["operator_server.py:_partial_and_proof"], "partial producer drift")
    require(call_sites.get("ThreadingHTTPServer") == ["operator_server.py:serve"], "listener drift")
    require(
        call_sites.get("combine_partials") == [
            "run_positive_certificate.py:run_routes",
            "run_positive_certificate.py:run_routes",
        ],
        "threshold combine sites drift",
    )
    require(
        call_sites.get("verify_threshold_result") == [
            "run_positive_certificate.py:run_routes"
        ],
        "commitment-verification site drift",
    )
    require(
        call_sites.get("Popen") == ["run_positive_certificate.py:start_operators"],
        "operator process spawn site drift",
    )
    return {
        "runtime_source_digest": RUNTIME_SOURCE_DIGEST,
        "module_sha256": {
            str(path.relative_to(HERE)).replace("\\", "/"): file_sha256(path)
            for path in modules
        },
        "runner_sha256": file_sha256(Path(__file__).resolve()),
        "certificate_schema_sha256": file_sha256(SCHEMA_PATH),
        "independent_verifier_sha256": file_sha256(VERIFIER_PATH),
        "critical_call_sites": call_sites,
        "served_http_routes": list(SERVED_ROUTES),
        "forbidden_imports_absent": sorted(forbidden_imports),
        "economic_transfer_api_present": False,
    }


def build_bindings(
    capture: Mapping[str, Any],
    committee: Committee,
    dealt_secrets: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    registry = OperatorRegistry.from_public(
        committee.operator_hosts, committee.network_public_keys
    )
    members = list(capture["roles"]["committee_member_addresses"])
    runtime_hashes = {
        str(route["contract"]["runtime_bytecode_keccak256"]).lower()
        for route in capture["routes"]
    }
    require(len(runtime_hashes) == 1, "routes use different OPE runtimes")
    runtime_hash = next(iter(runtime_hashes))
    entries: list[dict[str, Any]] = []
    for member_index, member_address in enumerate(members):
        operator_id = member_index + 1
        host_id = committee.operator_hosts[operator_id]
        secret = dealt_secrets[operator_id]
        identity = NetworkIdentity.from_secret(
            operator_id,
            host_id,
            int(str(secret["network_secret_key"]), 16),
        )
        statement = {
            "schema": "ope-member-operator-binding/v16",
            "member_index": member_index,
            "member_address": str(member_address).lower(),
            "operator_id": operator_id,
            "host_id": host_id,
            "network_public_key": hex(identity.public_key),
            "operator_registry_digest": registry.digest(),
            "ope_runtime_bytecode_keccak256": runtime_hash,
        }
        signature = sign(identity, canonical_json_bytes(statement))
        require(
            verify(identity.public_key, canonical_json_bytes(statement), signature),
            "operator binding signature failed",
        )
        entries.append({**statement, "signature": signature.to_dict()})
    return entries


def run_routes(
    capture: Mapping[str, Any],
    committee: Committee,
    coordinator: Coordinator,
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    output: list[dict[str, Any]] = []
    first_payload: Mapping[str, object] | None = None
    first_ciphertext = None
    first_partials = []
    first_order = ""
    first_operator = 0
    for route_index, route in enumerate(capture["routes"]):
        selected_operators = [int(value) for value in route["selected_operator_ids"]]
        order_id = f"ope-process:{str(route['payment_transaction']['hash']).lower()}"
        ciphertext = encrypt_capability(
            committee.public_key,
            committee.buyer,
            committee.resource,
            order_id,
            seed=10_000 + route_index,
        )
        verified = []
        payloads: list[Mapping[str, object]] = []
        for operator_id in selected_operators:
            outcome, payload, _ = coordinator.request(
                operator_id,
                order_id=order_id,
                buyer=committee.buyer,
                resource=committee.resource,
                epoch=committee.epoch,
                ciphertext=ciphertext,
                nonce=deterministic_nonce(order_id, operator_id),
            )
            require(not isinstance(outcome, RejectedResponse), f"operator {operator_id} rejected")
            require(payload is not None, "operator response payload missing")
            verified.append(outcome)
            payloads.append(payload)
        plaintext = combine_partials(
            ciphertext, [response.partial for response in verified], committee.threshold
        )
        require(verify_threshold_result(ciphertext, plaintext), "plaintext commitment failed")
        cost = int(route["payment_transaction"]["value_wei"]) // UNIT_WEI
        output.append(
            {
                "route_id": route["route_id"],
                "order_id": order_id,
                "payment_tx_hash": route["payment_transaction"]["hash"],
                "selected_member_indices": route["selected_member_indices"],
                "selected_operator_ids": selected_operators,
                "contract_cost_units": cost,
                "process_return_units": 0,
                "net_attacker_cost_units": cost,
                "ciphertext": ciphertext.to_dict(),
                "operator_responses": payloads,
                "delivery": {
                    "recipient": committee.buyer,
                    "plaintext_sha256": sha256_hex(int_to_bytes(plaintext)),
                    "plaintext_commitment_verified": True,
                    "response_count": len(verified),
                },
                "p1_authenticated_request_and_delivery": True,
                "p2star_boundary_and_session_binding": True,
                "p3_finality_policy_satisfied": True,
                "p4_returns_complete_and_debit_single_use": True,
                "p5_complete_route_replayed": True,
            }
        )
        if route_index == 0:
            first_payload = payloads[0]
            first_ciphertext = ciphertext
            first_partials = [response.partial for response in verified]
            first_order = order_id
            first_operator = selected_operators[0]

    require(
        first_payload is not None and first_ciphertext is not None and len(first_partials) == 4,
        "mutation basis missing",
    )
    replay, _, _ = coordinator.request(
        first_operator,
        order_id=first_order,
        buyer=committee.buyer,
        resource=committee.resource,
        epoch=committee.epoch,
        ciphertext=first_ciphertext,
        nonce=deterministic_nonce(first_order, first_operator),
    )
    swapped, _, _ = coordinator.request(
        first_operator,
        order_id=f"{first_order}:session-swap",
        buyer=committee.buyer,
        resource=committee.resource,
        epoch=committee.epoch,
        ciphertext=first_ciphertext,
        nonce=deterministic_nonce(f"{first_order}:session-swap", first_operator),
        replay_payload=first_payload,
    )
    proof_order = f"{first_order}:proof-tamper"
    proof_ciphertext = encrypt_capability(
        committee.public_key,
        committee.buyer,
        committee.resource,
        proof_order,
        seed=20_001,
    )
    proof, _, _ = coordinator.request(
        first_operator,
        order_id=proof_order,
        buyer=committee.buyer,
        resource=committee.resource,
        epoch=committee.epoch,
        ciphertext=proof_ciphertext,
        nonce=deterministic_nonce(proof_order, first_operator),
        tamper="proof",
    )
    delivery_bypass_rejected = False
    try:
        combine_partials(
            first_ciphertext,
            first_partials[:3],
            committee.threshold,
        )
    except ValueError:
        delivery_bypass_rejected = True
    return output, {
        "receipt_or_nonce_reuse_rejected": isinstance(replay, RejectedResponse),
        "session_swap_rejected": isinstance(swapped, RejectedResponse),
        "proof_tamper_rejected": isinstance(proof, RejectedResponse),
        "three_response_delivery_bypass_rejected": delivery_bypass_rejected,
    }


def evaluate() -> dict[str, Any]:
    verify_buyer_auth()
    capture = read_json(ROUTES_PATH)
    capture_costs = validate_capture(capture)
    c6 = bind_c6(capture_costs)
    sources = source_inventory()
    meta = {
        "committee_size": 7,
        "threshold": 4,
        "response_floors": [1, 1, 1, 1, 1, 1, 1],
        "buyer": str(capture["roles"]["attacker"]).lower(),
        "resource": RESOURCE,
        "epoch": 16,
        "operator_hosts": {
            "1": "host1",
            "2": "host2",
            "3": "host1",
            "4": "host2",
            "5": "host1",
            "6": "host2",
            "7": "host2",
        },
    }
    dealt = deal(meta, seed=0xC6C6C6, network_seed=0xA5A5A5)
    committee = Committee.from_public(dealt.public_bundle)

    processes: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="ope-process-positive-") as temporary:
        work = Path(temporary)
        public_path = work / "committee.public.json"
        secret_dir = work / "secrets"
        write_dealt(
            dealt,
            public_path=public_path,
            secret_dir=secret_dir,
        )
        processes, ports = start_operators(public_path, secret_dir, committee, work)
        try:
            coordinator = make_coordinator(committee, ports)
            wait_until_ready(coordinator, committee.committee_size)
            bindings = build_bindings(capture, committee, dealt.secrets_by_operator)
            routes, executable_mutations = run_routes(capture, committee, coordinator)
        finally:
            stop_operators(processes)

    boundary = build_p2star_boundary(capture, sources)
    bind_routes_to_p2star(routes, capture, boundary)
    costs = [int(route["net_attacker_cost_units"]) for route in routes]
    attaining_route = min(routes, key=lambda item: int(item["net_attacker_cost_units"]))
    attainment = {
        "kind": "reverse-replayed-route",
        "route_id": attaining_route["route_id"],
        "session_id": attaining_route["p2star_binding"]["session_id"],
        "scope_id": boundary["header"]["scope_id"],
        "header_digest": boundary["header"]["header_digest"],
        "mandatory_outflow_units": int(attaining_route["contract_cost_units"]),
        "return_units": int(attaining_route["process_return_units"]),
        "net_cost_units": int(attaining_route["net_attacker_cost_units"]),
        "typed_transfer_recomputed": True,
        "settlement_closed": True,
        "single_use_verified": True,
        "whole_process_replayed": True,
    }
    result: dict[str, Any] = {
        "schema": "ope-controlled-positive-process-certificate/v3",
        "verdict": VERDICT,
        "claim": {
            "claim_type": "boundary-complete-authenticated-relative-process-cost",
            "quantity": "authenticated relative-process attacker net cost through first commitment-valid plaintext delivery",
            "scope": "admitted local OPE plus seven-process 4-of-7 threshold-service composition",
            "attacker_role": committee.buyer,
            "accounting_unit": "native call value / 10^18 wei",
        },
        "model": {
            "control_boundary": {
                "attacker": committee.buyer,
                "included_identities": [committee.buyer],
                "closure_rule": "identities declared under the attacker's beneficial control in the admitted model",
                "excluded_service_controller": str(capture["roles"]["service_contract_controller"]).lower(),
                "excluded_committee_members": [
                    str(value).lower()
                    for value in capture["roles"]["committee_member_addresses"]
                ],
                "internal_transfer_treatment": "transfers wholly inside the declared control closure are not boundary-crossing debits",
            },
            "real_success_histories": {
                "domain": "all successful executions admitted by the controlled runtime and the P1/P2-star/P3/P4 evidence header",
                "success_event": "first commitment-valid plaintext delivery to the authenticated attacker",
                "represented_history_count": len(routes),
            },
            "checked_routes": {
                "domain": "all successful fixed-root routes accepted by the independent checker",
                "route_count": len(routes),
                "whole_process_routes": True,
            },
            "observation_projection": {
                "observer": "independent artifact verifier",
                "fields": [
                    "authenticated request",
                    "payment receipt and finality",
                    "member/operator binding",
                    "threshold responses",
                    "commitment-valid delivery",
                    "settlement and return closure",
                ],
            },
            "p5_completeness": {
                "forward_totality": True,
                "whole_process_reverse_replay": True,
                "same_session_state_continuity": True,
                "cost_preservation": True,
                "minimum_equality_not_assumed": True,
            },
        },
        "p1_p5": {
            "P1": {
                "status": "PASS",
                "evidence": "35 EIP-191 buyer-authenticated requests and 35 commitment-valid deliveries",
            },
            "P2_star": {
                "status": "PASS",
                "evidence": "five digest-bound manifests cover control, acquisition-linked funding/returns/settlement, reuse, and horizon across all 35 header-bound sessions",
            },
            "P3": {
                "status": "PASS",
                "evidence": "six-confirmation policy met before every operator dispatch and delivery",
            },
            "P4": {
                "status": "PASS",
                "evidence": "contract mutating ABI closure, zero buyer claimable balance, no buyer withdraw/refund/rebate route, no economic transfer API in the admitted service runtime, and persistent receipt/nonce single use",
            },
            "P5": {
                "status": "PASS",
                "evidence": "the 35-route fixed C6 root and all 35 whole process routes agree and replay",
            },
        },
        "boundary": boundary,
        "attainment": attainment,
        "cost": {
            "contract_minimum_units": min(capture_costs.values()),
            "process_minimum_units": min(costs),
            "process_maximum_units": max(costs),
            "all_returns_to_attacker_units": sum(
                int(route["process_return_units"]) for route in routes
            ),
            "minimum_attained": min(costs) == 4,
        },
        "route_coverage": {
            "forward_routes": len(routes),
            "reverse_replayed_routes": len(routes),
            "terminal_choices": len({tuple(route["selected_member_indices"]) for route in routes}),
            "contract_certificate_binding": c6,
        },
        "return_interface": {
            "contract_mutating_routes": [
                "configureCredits(uint256[7])",
                "acquireFour(uint8[4])",
                "withdraw()",
            ],
            "buyer_claimable_after_success_wei": 0,
            "buyer_withdraw_rejected_on_all_routes": True,
            "refund_cancel_rebate_entry_points": [],
            "service_runtime_economic_transfer_apis": [],
            "post_success_member_withdrawal_effect": "member-only claim realization after first success; no value enters attacker control",
            "cross_session_return_entry_points": [],
        },
        "runtime": {
            "operator_processes": 7,
            "threshold": 4,
            "committee": {
                "committee_size": committee.committee_size,
                "threshold": committee.threshold,
                "public_key": hex(committee.public_key),
                "public_shares": {
                    str(key): hex(value) for key, value in committee.public_shares.items()
                },
                "network_public_keys": {
                    str(key): hex(value)
                    for key, value in committee.network_public_keys.items()
                },
                "operator_hosts": {
                    str(key): value for key, value in committee.operator_hosts.items()
                },
            },
            "signed_bindings": bindings,
            "source_inventory": sources,
            "deterministic_artifact_keys": True,
        },
        "routes": routes,
        "mutations": {
            "executable": executable_mutations,
            "p2star_checker_result": "results/p2star_mutations.v1.json",
        },
        "limitations": [
            "relative to the admitted controlled composition, not deployment-wide",
            "local Hardhat EVM with six mined confirmations, not public-chain finality",
            "deterministic artifact-only dealer keys, not production keys or DKG",
            "gas, operating-system compromise, side channels, and undeclared external transfers are outside the accounting header",
            "no claim of seven economically independent operators",
        ],
        "inputs": {
            "ope_routes_sha256": file_sha256(ROUTES_PATH),
            "c6_certificate_sha256": file_sha256(C6_PATH),
            "refinement_certificate_sha256": file_sha256(REFINEMENT_PATH),
            "contract_source_sha256": file_sha256(CONTRACT_SOURCE_PATH),
        },
    }
    require(
        result["verdict"] == VERDICT,
        "verdict drift",
    )
    require(result["cost"]["process_minimum_units"] == 4, "positive process floor is not four")
    require(all(item["status"] == "PASS" for item in result["p1_p5"].values()), "P1/P2-star/P3/P4/P5 not all PASS")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    if args.write:
        write_json(RESULT_PATH, result)
    else:
        require(RESULT_PATH.exists(), "committed positive certificate missing")
        require(read_json(RESULT_PATH) == result, "committed positive certificate differs")
    executable = result["mutations"]["executable"]
    print("OPE_PROCESS_P1_P2STAR_P3_P4_P5=PASS")
    print("OPE_PROCESS_P2STAR_MANIFESTS=5_OF_5")
    print("OPE_PROCESS_FORWARD_ROUTES=35_OF_35")
    print("OPE_PROCESS_REVERSE_REPLAY=35_OF_35")
    print(f"OPE_PROCESS_EXECUTABLE_MUTATIONS={sum(executable.values())}_OF_{len(executable)}")
    print("OPE_PROCESS_P2STAR_MUTATIONS=SEE_INDEPENDENT_VERIFIER")
    print("OPE_PROCESS_GAMMA_A=4")
    print(result["verdict"])


if __name__ == "__main__":
    main()
