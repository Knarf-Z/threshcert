"""Four-valued gate verdicts and a three-valued report, over a two-host run.

Identical semantics to v2: a missing proof object yields
``FAIL_CLOSED_MISSING_EVIDENCE`` and an overall ``UNKNOWN``, never a refutation.
The certificate is derived from the execution's allocation witness and is never
the closed-form cover value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .ledger import OrderLedger
from .witness import (
    AggregationWitness,
    AllocationWitness,
    RouteCoverageEvidence,
    WitnessCheck,
    verify_allocation_witness,
)

PASS = "PASS"
FAIL_COUNTEREXAMPLE = "FAIL_COUNTEREXAMPLE"
FAIL_CLOSED_MISSING_EVIDENCE = "FAIL_CLOSED_MISSING_EVIDENCE"
NOT_APPLICABLE = "NOT_APPLICABLE"

CERTIFIED = "CERTIFIED"
REFUTED = "REFUTED"
UNKNOWN = "UNKNOWN"


@dataclass
class ExecutionView:
    """What the gates read about one attempted order."""

    order_id: str
    buyer: str
    consumer: str
    threshold: int
    counted_operator_ids: list[int]
    aggregate_valid: bool
    gateway_accepted: bool
    ledger: OrderLedger


@dataclass(frozen=True)
class GateVerdict:
    status: str
    reason: str
    witness: object | None = None

    @property
    def passed(self) -> bool:
        return self.status == PASS

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "reason": self.reason, "witness": self.witness}


@dataclass(frozen=True)
class EvidenceReport:
    gates: dict[str, GateVerdict]
    allocation_check: WitnessCheck
    execution_floor: int
    observed_outflow: int
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "gates": {name: verdict.to_dict() for name, verdict in self.gates.items()},
            "allocation_check": self.allocation_check.to_dict(),
            "execution_floor": self.execution_floor,
            "certificate_outcome": {"status": self.status, "floor": self.execution_floor},
            "observed_outflow": self.observed_outflow,
            "status": self.status,
        }


def _gate_b1(view: ExecutionView, aggregation: AggregationWitness) -> GateVerdict:
    if not aggregation.aggregate_valid:
        return GateVerdict(FAIL_COUNTEREXAMPLE, "no valid threshold aggregate was produced")
    if len(aggregation.operator_ids) < view.threshold:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "counted responder set is below threshold",
            {"counted": list(aggregation.operator_ids)},
        )
    if not view.gateway_accepted:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "usable capability was consumed by a principal other than the named buyer",
            {"named_buyer": view.buyer, "consumer": view.consumer},
        )
    return GateVerdict(PASS, "valid threshold plaintext consumed by the named buyer")


def _gate_b2(view: ExecutionView) -> GateVerdict:
    ledger = view.ledger
    if ledger.deposit_source != "buyer" or ledger.sponsor_funding:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "the counted debit did not originate in the named-buyer control closure",
            {"deposit_source": ledger.deposit_source},
        )
    return GateVerdict(PASS, "deposit funded by the named buyer")


def _gate_b3(view: ExecutionView, b1: GateVerdict) -> GateVerdict:
    if b1.status != PASS:
        return GateVerdict(NOT_APPLICABLE, "no named-buyer usable delivery to be atomic with")
    counted = set(view.counted_operator_ids)
    records = [record for record in view.ledger.responses if record.operator_id in counted]
    missing = [record.operator_id for record in records if not record.ordering_evidence]
    if missing:
        return GateVerdict(
            FAIL_CLOSED_MISSING_EVIDENCE,
            "credit/release ordering is not recorded for every counted response",
            {"operators_without_ordering_evidence": missing},
        )
    late = [
        record.operator_id
        for record in records
        if record.credit_step is None or record.credit_step > record.release_step
    ]
    if late:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "a usable response was released before its irreversible credit",
            {"operators_released_early": late},
        )
    return GateVerdict(PASS, "credit precedes every counted response")


def _gate_b4(view: ExecutionView) -> GateVerdict:
    unaccounted = [record.to_dict() for record in view.ledger.returns if not record.accounted]
    if unaccounted:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "a return into the buyer control closure is not enumerated and subtracted",
            {"unaccounted_returns": unaccounted},
        )
    if view.ledger.escrow_remaining:
        return GateVerdict(
            FAIL_CLOSED_MISSING_EVIDENCE,
            "escrow remainder was never dispositioned",
            {"escrow_remaining": view.ledger.escrow_remaining},
        )
    return GateVerdict(PASS, "every refund, reimbursement and funding edge is enumerated and netted")


def _gate_b5(view: ExecutionView, coverage: RouteCoverageEvidence) -> GateVerdict:
    if coverage.status == "UNKNOWN":
        return GateVerdict(
            FAIL_CLOSED_MISSING_EVIDENCE,
            "no route-coverage proof was supplied for the declared language",
        )
    if coverage.status == "REFUTED":
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "an unmapped response route carries a usable delivery",
            coverage.bypass_trace,
        )
    counted = set(view.counted_operator_ids)
    records = [record for record in view.ledger.responses if record.operator_id in counted]
    stray = sorted({record.route for record in records} - set(coverage.covered_routes))
    if stray:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "a counted response uses a route outside the covered catalog",
            {"uncovered_routes": stray},
        )
    return GateVerdict(PASS, "all counted responses follow the covered paid route")


def evaluate(
    view: ExecutionView,
    aggregation: AggregationWitness,
    allocation: AllocationWitness,
    coverage: RouteCoverageEvidence,
    floors: Sequence[int],
) -> EvidenceReport:
    observed = view.ledger.named_buyer_net_outflow
    floor_map = {operator_id: floors[operator_id - 1] for operator_id in view.counted_operator_ids}
    allocation_check = verify_allocation_witness(aggregation, allocation, floor_map, observed)

    b1 = _gate_b1(view, aggregation)
    gates = {
        "B1": b1,
        "B2": _gate_b2(view),
        "B3": _gate_b3(view, b1),
        "B4": _gate_b4(view),
        "B5": _gate_b5(view, coverage),
    }

    statuses = [verdict.status for verdict in gates.values()]
    if FAIL_COUNTEREXAMPLE in statuses:
        status = REFUTED
    elif FAIL_CLOSED_MISSING_EVIDENCE in statuses or not allocation_check.ok:
        status = UNKNOWN
    else:
        status = CERTIFIED

    return EvidenceReport(
        gates=gates,
        allocation_check=allocation_check,
        execution_floor=allocation.total_allocated if status == CERTIFIED and allocation_check.ok else 0,
        observed_outflow=observed,
        status=status,
    )
