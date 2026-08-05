"""Proof objects for the hypotheses of the threshold-response certificate.

Three witnesses are emitted per execution and verified independently of the
gate logic:

``aggregation_witness``
    Fixes ``Q_c(h)``: the counted responder set is *named by the transcript*
    rather than inferred by the evaluator.

``allocation_witness``
    Instantiates (C2): per-responder debit/refund/funding amounts with globally
    unique debit identifiers, bound to the same responder bitmap as the
    aggregation witness.

``route_coverage_evidence``
    Turns (B5) from a boolean argument into an input proof object with three
    possible statuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .utils import canonical_json_bytes, sha256_hex


def bitmap_of(operator_ids: Sequence[int]) -> str:
    mask = 0
    for operator_id in operator_ids:
        if operator_id <= 0:
            raise ValueError("operator ids are 1-based")
        mask |= 1 << (operator_id - 1)
    return f"0x{mask:02x}"


def ids_of_bitmap(bitmap: str) -> list[int]:
    mask = int(bitmap, 16)
    out: list[int] = []
    index = 0
    while mask:
        index += 1
        if mask & 1:
            out.append(index)
        mask >>= 1
    return out


@dataclass(frozen=True)
class AggregationWitness:
    order_id: str
    buyer: str
    resource: str
    epoch: int
    responder_bitmap: str
    operator_ids: tuple[int, ...]
    partial_response_hashes: tuple[str, ...]
    aggregate_valid: bool
    plaintext_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "aggregation_witness",
            "order_id": self.order_id,
            "buyer": self.buyer,
            "resource": self.resource,
            "epoch": self.epoch,
            "responder_bitmap": self.responder_bitmap,
            "operator_ids": list(self.operator_ids),
            "partial_response_hashes": list(self.partial_response_hashes),
            "aggregate_valid": self.aggregate_valid,
            "plaintext_hash": self.plaintext_hash,
        }


@dataclass(frozen=True)
class AllocationEntry:
    operator_id: int
    responder_bitmap: str
    response_hash: str
    debit_id: str | None
    debit: int
    refund_ids: tuple[str, ...]
    refund: int
    funding_ids: tuple[str, ...]
    external_funding: int

    @property
    def net_allocated_outflow(self) -> int:
        return self.debit - self.refund - self.external_funding

    def to_dict(self) -> dict[str, object]:
        return {
            "operator_id": self.operator_id,
            "responder_bitmap": self.responder_bitmap,
            "response_hash": self.response_hash,
            "debit_id": self.debit_id,
            "debit": self.debit,
            "refund_ids": list(self.refund_ids),
            "refund": self.refund,
            "funding_ids": list(self.funding_ids),
            "external_funding": self.external_funding,
            "net_allocated_outflow": self.net_allocated_outflow,
        }


@dataclass(frozen=True)
class AllocationWitness:
    order_id: str
    responder_bitmap: str
    entries: tuple[AllocationEntry, ...]

    @property
    def total_allocated(self) -> int:
        return sum(entry.net_allocated_outflow for entry in self.entries)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "allocation_witness",
            "order_id": self.order_id,
            "responder_bitmap": self.responder_bitmap,
            "entries": [entry.to_dict() for entry in self.entries],
            "total_allocated": self.total_allocated,
        }


@dataclass(frozen=True)
class RouteCoverageEvidence:
    status: str  # PROVED | REFUTED | UNKNOWN
    scope_hash: str
    route_catalog_hash: str
    covered_routes: tuple[str, ...]
    excluded_routes: tuple[str, ...]
    proof_kernel: str
    bypass_trace: dict[str, object] | None = None
    deployment_wide: bool = False
    coverage_scope: str = "declared finite program language"

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "route_coverage_evidence",
            "status": self.status,
            "scope_hash": self.scope_hash,
            "route_catalog_hash": self.route_catalog_hash,
            "covered_routes": list(self.covered_routes),
            "excluded_routes": list(self.excluded_routes),
            "proof_kernel": self.proof_kernel,
            "bypass_trace": self.bypass_trace,
            "deployment_wide": self.deployment_wide,
            "coverage_scope": self.coverage_scope,
        }


@dataclass
class WitnessCheck:
    ok: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "failures": list(self.failures)}


def verify_allocation_witness(
    aggregation: AggregationWitness,
    allocation: AllocationWitness,
    floors: dict[int, int],
    observed_outflow: int,
) -> WitnessCheck:
    """Check the six clauses (C2) requires of an allocation witness."""
    failures: list[str] = []

    if allocation.order_id != aggregation.order_id:
        failures.append("order_id mismatch between aggregation and allocation witnesses")
    if allocation.responder_bitmap != aggregation.responder_bitmap:
        failures.append("responder bitmap mismatch between aggregation and allocation witnesses")

    counted = set(aggregation.operator_ids)
    hash_by_operator = dict(zip(aggregation.operator_ids, aggregation.partial_response_hashes))
    allocated = {entry.operator_id for entry in allocation.entries}
    if allocated != counted:
        failures.append(f"allocation covers {sorted(allocated)} but the counted set is {sorted(counted)}")

    seen_debit_ids: set[str] = set()
    seen_return_ids: set[str] = set()
    for entry in allocation.entries:
        # 1. the operator is in the aggregation bitmap
        if entry.operator_id not in counted:
            failures.append(f"operator {entry.operator_id} is not in the aggregation bitmap")
        if entry.responder_bitmap != aggregation.responder_bitmap:
            failures.append(f"operator {entry.operator_id} carries a foreign responder bitmap")
        # 2. the response hash agrees with the aggregation witness
        if hash_by_operator.get(entry.operator_id) != entry.response_hash:
            failures.append(f"operator {entry.operator_id} response hash differs from the aggregation witness")
        # 3. debit identifiers are globally unique
        if entry.debit_id is None:
            failures.append(f"operator {entry.operator_id} has no debit identifier")
        elif entry.debit_id in seen_debit_ids:
            failures.append(f"debit identifier {entry.debit_id} allocated more than once")
        else:
            seen_debit_ids.add(entry.debit_id)
        # 4. no refund or funding identifier is allocated twice
        for return_id in tuple(entry.refund_ids) + tuple(entry.funding_ids):
            if return_id in seen_return_ids:
                failures.append(f"return identifier {return_id} allocated more than once")
            else:
                seen_return_ids.add(return_id)
        # 5. the per-member floor is covered
        floor = floors.get(entry.operator_id, 0)
        if entry.net_allocated_outflow < floor:
            failures.append(
                f"operator {entry.operator_id} nets {entry.net_allocated_outflow} below its floor {floor}"
            )

    # 6. the allocation does not exceed the realized outflow
    if allocation.total_allocated > observed_outflow:
        failures.append(
            f"allocated total {allocation.total_allocated} exceeds the realized outflow {observed_outflow}"
        )

    return WitnessCheck(ok=not failures, failures=failures)


def scope_hash(buyer: str, resource: str, threshold: int, committee_size: int) -> str:
    return sha256_hex(
        canonical_json_bytes(
            {
                "buyer": buyer,
                "resource": resource,
                "threshold": threshold,
                "committee_size": committee_size,
            }
        )
    )


def catalog_hash(routes: Sequence[str]) -> str:
    return sha256_hex(canonical_json_bytes(sorted(routes)))
