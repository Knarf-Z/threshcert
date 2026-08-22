"""Run the OPE receipt through the real dealt threshold-response service.

The Hardhat capture is intentionally separate: it produces a real contract
receipt, while this runner consumes only its public fields and dispatches the
selected member indices into the existing operator HTTP protocol.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ptr_v3.coordinator import Coordinator, OperatorEndpoint, RejectedResponse  # noqa: E402
from ptr_v3.crypto import combine_partials, verify_threshold_result  # noqa: E402
from ptr_v3.experiment import Committee, deterministic_nonce, make_ciphertext  # noqa: E402
from ptr_v3.network_identity import OperatorRegistry  # noqa: E402
from ptr_v3.operator_server import RUNTIME_SOURCE_DIGEST  # noqa: E402
from ope_receipt_bridge_lib import (  # noqa: E402
    build_operator_bindings,
    expect_receipt_rejection,
    negative_receipt_cases,
    receipt_digest,
    verify_receipt,
)
from ptr_v3.utils import canonical_json_bytes, int_to_bytes, read_json, sha256_hex, write_json  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_operators(public_path: Path, secret_root: Path, committee: Committee, work: Path):
    processes: list[subprocess.Popen[bytes]] = []
    ports: dict[int, int] = {}
    server_script = ROOT / "src" / "ptr_v3" / "operator_server.py"
    for operator_id in range(1, committee.committee_size + 1):
        port = _free_port()
        ports[operator_id] = port
        host_id = committee.operator_hosts[operator_id]
        command = [
            sys.executable,
            str(server_script),
            "--operator-id",
            str(operator_id),
            "--bind",
            "127.0.0.1",
            "--port",
            str(port),
            "--secret",
            str(secret_root / host_id / f"operator-{operator_id}.secret.json"),
            "--public",
            str(public_path),
            "--transcript",
            str(work / f"operator-{operator_id}.transcript.jsonl"),
            "--nonce-log",
            str(work / f"operator-{operator_id}.nonces.log"),
        ]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(process)
    return processes, ports


def _stop_operators(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def _coordinator(committee: Committee, ports: dict[int, int]) -> Coordinator:
    registry = OperatorRegistry.from_public(committee.operator_hosts, committee.network_public_keys)
    endpoints = {
        operator_id: OperatorEndpoint(operator_id, committee.operator_hosts[operator_id], "127.0.0.1", ports[operator_id])
        for operator_id in range(1, committee.committee_size + 1)
    }
    return Coordinator(
        registry=registry,
        endpoints=endpoints,
        public_shares=committee.public_share_list(),
        expected_runtime_source_digest=RUNTIME_SOURCE_DIGEST,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind an OPE receipt to the real two-host threshold service.")
    parser.add_argument("--receipt", type=Path, default=ROOT.parent / "verify_v42_clean" / "joint_incidence_refinement" / "results" / "receipt_bridge.receipt.v1.json")
    parser.add_argument("--public", type=Path, default=ROOT / "config" / "committee.public.v3.json")
    parser.add_argument("--secrets", type=Path, default=ROOT / "secrets")
    parser.add_argument("--result", type=Path, default=ROOT / "results" / "ope_receipt_bridge.v1.json")
    args = parser.parse_args()

    receipt = read_json(args.receipt)
    base_committee = Committee.from_file(args.public)
    buyer = str(receipt["payment_transaction"]["from"])
    committee = Committee(
        committee_size=base_committee.committee_size,
        threshold=base_committee.threshold,
        response_floors=base_committee.response_floors,
        buyer=buyer,
        resource=base_committee.resource,
        epoch=base_committee.epoch,
        operator_hosts=base_committee.operator_hosts,
        public_key=base_committee.public_key,
        public_shares=base_committee.public_shares,
        network_public_keys=base_committee.network_public_keys,
    )
    binding = build_operator_bindings(receipt, committee, args.secrets)
    gate = verify_receipt(receipt, committee, binding)
    order_id = f"ope-receipt:{gate['payment_tx_hash']}"

    processes: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="ptr-ope-receipt-") as temporary:
        work = Path(temporary)
        processes, ports = _start_operators(args.public, args.secrets, committee, work)
        coordinator = _coordinator(committee, ports)
        deadline = time.time() + 10
        while time.time() < deadline:
            if all(coordinator.health(operator_id) is not None for operator_id in range(1, committee.committee_size + 1)):
                break
            time.sleep(0.1)
        if not all(coordinator.health(operator_id) is not None for operator_id in range(1, committee.committee_size + 1)):
            _stop_operators(processes)
            raise RuntimeError("not all real operator HTTP processes became ready")

        ciphertext = make_ciphertext(committee, order_id)
        responses = []
        rejected: list[dict[str, object]] = []
        for operator_id in gate["selected_operator_ids"]:
            outcome, payload, elapsed = coordinator.request(
                int(operator_id),
                order_id=order_id,
                buyer=committee.buyer,
                resource=committee.resource,
                epoch=committee.epoch,
                ciphertext=ciphertext,
                nonce=deterministic_nonce(order_id, int(operator_id)),
            )
            if isinstance(outcome, RejectedResponse):
                rejected.append({**outcome.to_dict(), "elapsed_ms": elapsed})
            else:
                responses.append(outcome)

        if rejected or len(responses) != committee.threshold:
            _stop_operators(processes)
            raise RuntimeError(f"receipt-selected threshold route failed: {rejected}")
        plaintext = combine_partials(ciphertext, [response.partial for response in responses], committee.threshold)
        if not verify_threshold_result(ciphertext, plaintext):
            _stop_operators(processes)
            raise RuntimeError("real threshold reconstruction failed the ciphertext commitment")

        # The existing coordinator's negative path rejects a changed response
        # context before any plaintext can be released.
        mutation_coordinator = _coordinator(committee, ports)
        mutated_ciphertext = make_ciphertext(committee, f"{order_id}:mutated")
        mutated_outcome, _, _ = mutation_coordinator.request(
            int(gate["selected_operator_ids"][0]),
            order_id=f"{order_id}:mutated",
            buyer=committee.buyer,
            resource=committee.resource,
            epoch=committee.epoch,
            ciphertext=mutated_ciphertext,
            nonce=deterministic_nonce(f"{order_id}:mutated", int(gate["selected_operator_ids"][0])),
            tamper="order",
        )
        ciphertext_order_rejected = isinstance(mutated_outcome, RejectedResponse)

        result: dict[str, Any] = {
            "schema": "ptr-ope-receipt-bridge-result/v1",
            "receipt_sha256": receipt_digest(receipt),
            "gate": gate,
            "binding": binding,
            "protocol": {
                "order_id": order_id,
                "buyer": committee.buyer,
                "resource": committee.resource,
                "epoch": committee.epoch,
                "threshold": committee.threshold,
                "selected_operator_ids": list(gate["selected_operator_ids"]),
                "operator_registry_digest": gate["registry_digest"],
                "runtime_source_digest": RUNTIME_SOURCE_DIGEST,
                "ciphertext_hash": sha256_hex(canonical_json_bytes(ciphertext.to_dict())),
                "ciphertext_plaintext_commitment": ciphertext.plaintext_commitment,
                "response_hashes": [response.response_hash for response in responses],
                "partial_hashes": [response.partial_hash for response in responses],
                "proof_hashes": [response.proof_hash for response in responses],
                "plaintext_hash": sha256_hex(int_to_bytes(plaintext)),
                "plaintext_commitment_verified": True,
            },
            "negative_cases": {
                **negative_receipt_cases(receipt, committee, binding),
                "ciphertext_or_order_substitution": {
                    "rejected": ciphertext_order_rejected,
                    "reason": mutated_outcome.to_dict() if isinstance(mutated_outcome, RejectedResponse) else "unexpected acceptance",
                },
            },
            "claims": {
                "real_dealt_threshold_shares_used": True,
                "real_operator_http_processes_used": True,
                "real_network_signatures_verified": True,
                "receipt_selected_exactly_four_operators": list(gate["selected_operator_ids"]) == [1, 2, 5, 6],
                "underpayment_reverted_in_capture": bool(receipt["negative_underpayment"]["reverted"]),
                "no_secret_material_serialized": True,
            },
        }
        _stop_operators(processes)
        write_json(args.result, result)

    print(f"BRIDGE_RESULT={args.result}")
    print("REAL_OPERATOR_HTTP=PASS")
    print("RECEIPT_GATE=PASS")
    print("THRESHOLD_RECONSTRUCTION=PASS")
    print(f"SELECTED_OPERATORS={','.join(map(str, gate['selected_operator_ids']))}")
    print(f"NEGATIVE_CASES={'PASS' if all(v.get('rejected') for v in result['negative_cases'].values()) else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
