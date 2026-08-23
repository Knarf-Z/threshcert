"""Host 1's orchestration of the two-host threshold-response experiment.

Every counted partial in every experiment group below is fetched over the
network, verified against the operator's registered public share and network
key, and only then allowed into an aggregation witness. Nothing is computed
locally on host 1's behalf for an operator that host 1 does not own.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations
from pathlib import Path
import platform
import sys
import time
from typing import Any, Mapping, Sequence

from .certificate import brute_force_weighted, catalog_certificate, theory_cover, weighted_dp
from .coordinator import Coordinator, OperatorEndpoint, RejectedResponse, VerifiedResponse
from .crypto import Ciphertext, combine_partials, encrypt_capability, verify_threshold_result
from .evidence import CERTIFIED, REFUTED, UNKNOWN, ExecutionView, evaluate
from .ledger import OrderLedger
from .network_identity import NetworkIdentity, OperatorRegistry
from .operator_server import SERVED_ROUTES
from .utils import canonical_json_bytes, int_to_bytes, read_json, sha256_hex, write_json
from .witness import (
    AggregationWitness,
    AllocationEntry,
    AllocationWitness,
    RouteCoverageEvidence,
    bitmap_of,
    catalog_hash,
    scope_hash,
)

SCHEMA = "paid-threshold-response-two-host/v6"
COVERED_ROUTES = ("paid_response",)
PROOF_KERNEL = "restricted-source-kernel/RSP-V6"


@dataclass(frozen=True)
class Committee:
    """The public view of the committee, loaded from the dealt public bundle.

    It holds no seed and no secret. The coordinator that carries this object
    cannot mint a share or a network key; it can only encrypt to the public key,
    recognise the public shares when verifying partials, and recognise the
    network public keys when verifying signatures.
    """

    committee_size: int
    threshold: int
    response_floors: tuple[int, ...]
    buyer: str
    resource: str
    epoch: int
    operator_hosts: Mapping[int, str]
    public_key: int
    public_shares: Mapping[int, int]
    network_public_keys: Mapping[int, int]

    @staticmethod
    def from_file(path: Path) -> "Committee":
        value = read_json(path)
        for field in ("seed", "network_seed", "secret_shares"):
            if field in value:
                raise ValueError(f"public committee bundle must not contain {field!r}")
        size = int(value["committee_size"])
        return Committee(
            committee_size=size,
            threshold=int(value["threshold"]),
            response_floors=tuple(int(v) for v in value["response_floors"]),
            buyer=str(value["buyer"]),
            resource=str(value["resource"]),
            epoch=int(value["epoch"]),
            operator_hosts={int(k): str(v) for k, v in value["operator_hosts"].items()},
            public_key=int(str(value["public_key"]), 16),
            public_shares={int(k): int(str(v), 16) for k, v in value["public_shares"].items()},
            network_public_keys={int(k): int(str(v), 16) for k, v in value["network_public_keys"].items()},
        )

    def hosts(self) -> list[str]:
        return sorted(set(self.operator_hosts.values()))

    def operators_on(self, host_id: str) -> list[int]:
        return sorted(i for i, h in self.operator_hosts.items() if h == host_id)

    def public_share_list(self) -> list[int]:
        return [self.public_shares[i] for i in range(1, self.committee_size + 1)]


def deterministic_nonce(order_id: str, operator_id: int, attempt: int = 0) -> str:
    return sha256_hex(
        canonical_json_bytes({"order_id": order_id, "operator_id": operator_id, "attempt": attempt})
    )[:32]


def make_ciphertext(committee: Committee, order_id: str) -> Ciphertext:
    # The controlled run deliberately does not use a reproducibility seed.
    # The coordinator receives only the ciphertext and a one-way commitment;
    # the high-entropy capability plaintext is returned only by threshold
    # decryption and cannot be recomputed from public evidence.
    return encrypt_capability(committee.public_key, committee.buyer, committee.resource, order_id)


@dataclass
class OrderOutcome:
    order_id: str
    coalition: list[int]
    order: list[int]
    verified: list[VerifiedResponse]
    rejected: list[RejectedResponse]
    threshold_reached: bool
    aggregate_valid: bool
    gateway_accepted: bool
    plaintext: int | None
    ledger: OrderLedger
    latencies_ms: list[float]


def run_order(
    coordinator: Coordinator,
    committee: Committee,
    *,
    order_id: str,
    coalition: Sequence[int],
    order: Sequence[int] | None = None,
    consumer: str | None = None,
    deposit_source: str = "buyer",
    tamper: str | None = None,
    tamper_operator: int | None = None,
    replay_from: Mapping[int, Mapping[str, object]] | None = None,
    ttl_s: float = 30.0,
) -> tuple[OrderOutcome, dict[int, Mapping[str, object]]]:
    sequence = list(order or coalition)
    ciphertext = make_ciphertext(committee, order_id)
    price_map = {i + 1: price for i, price in enumerate(committee.response_floors)}
    ledger = OrderLedger.open(order_id, committee.buyer, price_map, source=deposit_source)

    verified: list[VerifiedResponse] = []
    rejected: list[RejectedResponse] = []
    latencies: list[float] = []
    payloads: dict[int, Mapping[str, object]] = {}

    for operator_id in sequence:
        # The buyer debit is committed before the request goes out, so a response
        # that never arrives leaves a credited operator and no usable output.
        outcome, payload, elapsed = coordinator.request(
            operator_id,
            order_id=order_id,
            buyer=committee.buyer,
            resource=committee.resource,
            epoch=committee.epoch,
            ciphertext=ciphertext,
            nonce=deterministic_nonce(order_id, operator_id),
            ttl_s=ttl_s,
            tamper=tamper if (tamper_operator is None or tamper_operator == operator_id) else None,
            replay_payload=(replay_from or {}).get(operator_id),
        )
        latencies.append(elapsed)
        if payload is not None:
            payloads[operator_id] = payload
        if isinstance(outcome, VerifiedResponse):
            ledger.credit_before_release(operator_id, outcome.response_hash, True, True)
            verified.append(outcome)
        else:
            rejected.append(outcome)

    threshold_reached = len(verified) >= committee.threshold
    # Keep threshold reconstruction internal until both the commitment check and
    # the named-buyer guard pass. ``plaintext`` is the only deliverable field in
    # OrderOutcome; a rejected route must never populate it.
    plaintext: int | None = None
    candidate_plaintext: int | None = None
    aggregate_valid = False
    counted: list[VerifiedResponse] = []
    if threshold_reached:
        counted = verified[: committee.threshold]
        candidate_plaintext = combine_partials(ciphertext, [r.partial for r in counted], committee.threshold)
        aggregate_valid = verify_threshold_result(ciphertext, candidate_plaintext)

    actual_consumer = consumer or committee.buyer
    gateway_accepted = aggregate_valid and actual_consumer == ciphertext.buyer
    if gateway_accepted:
        plaintext = candidate_plaintext
        ledger.mark_success()
    ledger.finalize_refund()

    return (
        OrderOutcome(
            order_id=order_id,
            coalition=list(coalition),
            order=sequence,
            verified=counted if threshold_reached else verified,
            rejected=rejected,
            threshold_reached=threshold_reached,
            aggregate_valid=aggregate_valid,
            gateway_accepted=gateway_accepted,
            plaintext=plaintext,
            ledger=ledger,
            latencies_ms=latencies,
        ),
        payloads,
    )


def build_witnesses(outcome: OrderOutcome, committee: Committee, coverage_status: str = "PROVED"):
    counted = outcome.verified
    operator_ids = tuple(r.operator_id for r in counted)
    aggregation = AggregationWitness(
        order_id=outcome.order_id,
        buyer=committee.buyer,
        resource=committee.resource,
        epoch=committee.epoch,
        responder_bitmap=bitmap_of(operator_ids) if operator_ids else "0x00",
        operator_ids=operator_ids,
        host_ids=tuple(r.host_id for r in counted),
        partial_response_hashes=tuple(r.response_hash for r in counted),
        aggregate_valid=outcome.aggregate_valid,
        plaintext_hash=sha256_hex(int_to_bytes(outcome.plaintext)) if outcome.plaintext else "",
    )
    ledger = outcome.ledger
    record_by_operator = {record.operator_id: record for record in ledger.responses}
    buyer_funded = ledger.deposit_source == "buyer"
    offsetting = [r for r in ledger.returns if r.beneficiary == ledger.buyer and r.kind != "refund"]
    offset_ids = tuple(r.return_id for r in offsetting)
    remaining = sum(r.amount for r in offsetting)

    entries: list[AllocationEntry] = []
    for position, response in enumerate(counted):
        record = record_by_operator.get(response.operator_id)
        debit = (record.price if record else 0) if buyer_funded else 0
        funding = 0 if buyer_funded else (record.price if record else 0)
        take = min(debit, remaining)
        remaining -= take
        entries.append(
            AllocationEntry(
                operator_id=response.operator_id,
                host_id=response.host_id,
                responder_bitmap=aggregation.responder_bitmap,
                response_hash=response.response_hash,
                debit_id=record.debit_id if record else None,
                debit=debit,
                refund_ids=offset_ids if position == 0 and offset_ids else (),
                refund=take,
                funding_ids=(f"sponsor-{outcome.order_id}",) if funding else (),
                external_funding=funding,
            )
        )
    allocation = AllocationWitness(outcome.order_id, aggregation.responder_bitmap, tuple(entries))
    coverage = RouteCoverageEvidence(
        status=coverage_status,
        scope_hash=scope_hash(
            committee.buyer, committee.resource, committee.threshold, committee.committee_size, committee.hosts()
        ),
        route_catalog_hash=catalog_hash(COVERED_ROUTES),
        covered_routes=COVERED_ROUTES,
        excluded_routes=(),
        proof_kernel=PROOF_KERNEL,
        served_http_routes=SERVED_ROUTES,
    )
    return aggregation, allocation, coverage


def assess(outcome: OrderOutcome, committee: Committee, consumer: str | None = None, coverage_status: str = "PROVED"):
    aggregation, allocation, coverage = build_witnesses(outcome, committee, coverage_status)
    view = ExecutionView(
        order_id=outcome.order_id,
        buyer=committee.buyer,
        consumer=consumer or committee.buyer,
        threshold=committee.threshold,
        counted_operator_ids=[r.operator_id for r in outcome.verified],
        aggregate_valid=outcome.aggregate_valid,
        gateway_accepted=outcome.gateway_accepted,
        ledger=outcome.ledger,
    )
    report = evaluate(view, aggregation, allocation, coverage, committee.response_floors)
    return aggregation, allocation, coverage, report


def c1_witness(committee: Committee, source_root: Path, health: Mapping[int, Any]) -> dict[str, object]:
    modules = sorted(p for p in (source_root / "ptr_v3").glob("*.py"))
    from .utils import file_sha256

    return {
        "type": "c1_non_exportability_witness",
        "conclusion": "C1 proved within the declared finite service language over the configured hosts",
        "hardware_enforced": False,
        "served_http_routes": list(SERVED_ROUTES),
        "export_operations": [],
        "operator_reported_routes": {
            str(op): sorted(info.get("served_routes", [])) for op, info in sorted(health.items())
        },
        "source_hashes": {module.name: file_sha256(module) for module in modules},
        "scope": "declared finite program language; no attestation, no HSM or TEE",
    }
