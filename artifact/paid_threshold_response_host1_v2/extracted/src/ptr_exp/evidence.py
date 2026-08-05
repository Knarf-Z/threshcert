"""Four-valued gate verdicts and a three-valued overall report.

Each gate returns one of ``PASS``, ``FAIL_COUNTEREXAMPLE``,
``FAIL_CLOSED_MISSING_EVIDENCE`` or ``NOT_APPLICABLE``.  The overall verdict is
``CERTIFIED``, ``REFUTED`` or ``UNKNOWN``; a missing proof object never reads as
a refutation.

The reported certificate is *derived from the execution ledger*, never from the
closed-form cover value.  The closed form is computed separately by
``certificate.theory_cover`` so that the two agree only if the experiment makes
them agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .protocol import ExecutionResult
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
    execution_floor: int | None
    observed_outflow: int
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "gates": {name: verdict.to_dict() for name, verdict in self.gates.items()},
            "allocation_check": self.allocation_check.to_dict(),
            "execution_floor": self.execution_floor,
            "observed_outflow": self.observed_outflow,
            "status": self.status,
        }


def _gate_b1(result: ExecutionResult, aggregation: AggregationWitness) -> GateVerdict:
    if not aggregation.aggregate_valid:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "no valid threshold aggregate was produced",
            {"aggregate_valid": False},
        )
    if len(aggregation.operator_ids) < result.threshold:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "counted responder set is below threshold",
            {"counted": list(aggregation.operator_ids)},
        )
    if not result.gateway_accepted:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "usable capability was consumed by a principal other than the named buyer",
            {"named_buyer": result.buyer, "consumer": result.consumer},
        )
    return GateVerdict(PASS, "valid threshold plaintext consumed by the named buyer")


def _gate_b2(result: ExecutionResult) -> GateVerdict:
    ledger = result.ledger
    if ledger.deposit_source != "buyer" or ledger.sponsor_funding:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "the counted debit did not originate in the named-buyer control closure",
            {"deposit_source": ledger.deposit_source, "sponsor_funding": ledger.sponsor_funding},
        )
    return GateVerdict(PASS, "deposit funded by the named buyer")


def _gate_b3(result: ExecutionResult, b1: GateVerdict) -> GateVerdict:
    """Atomicity is only meaningful once a named-buyer usable delivery exists."""
    if b1.status != PASS:
        return GateVerdict(NOT_APPLICABLE, "no named-buyer usable delivery to be atomic with")
    counted = {response.operator_id for response in result.used_responses}
    records = [record for record in result.ledger.responses if record.operator_id in counted]
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
    return GateVerdict(PASS, "credit precedes every released counted partial")


def _gate_b4(result: ExecutionResult) -> GateVerdict:
    """Return/funding/control closure only: is every return enumerated and netted?"""
    unaccounted = [record.to_dict() for record in result.ledger.returns if not record.accounted]
    if unaccounted:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "a return into the buyer control closure is not enumerated and subtracted",
            {"unaccounted_returns": unaccounted},
        )
    if result.ledger.escrow_remaining:
        return GateVerdict(
            FAIL_CLOSED_MISSING_EVIDENCE,
            "escrow remainder was never dispositioned",
            {"escrow_remaining": result.ledger.escrow_remaining},
        )
    return GateVerdict(PASS, "every refund, reimbursement and funding edge is enumerated and netted")


def _gate_b5(result: ExecutionResult, coverage: RouteCoverageEvidence) -> GateVerdict:
    if coverage.status == "UNKNOWN":
        return GateVerdict(
            FAIL_CLOSED_MISSING_EVIDENCE,
            "no route-coverage proof was supplied for the declared language",
            {"coverage_status": coverage.status},
        )
    if coverage.status == "REFUTED":
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "an unmapped response route carries a usable delivery",
            coverage.bypass_trace,
        )
    counted = {response.operator_id for response in result.used_responses}
    records = [record for record in result.ledger.responses if record.operator_id in counted]
    stray = sorted({record.route for record in records} - set(coverage.covered_routes))
    if stray:
        return GateVerdict(
            FAIL_COUNTEREXAMPLE,
            "a counted response uses a route outside the covered catalog",
            {"uncovered_routes": stray},
        )
    return GateVerdict(PASS, "all counted responses follow the covered paid route")


def evaluate_execution(
    result: ExecutionResult,
    aggregation: AggregationWitness,
    allocation: AllocationWitness,
    coverage: RouteCoverageEvidence,
    floors: Sequence[int],
) -> EvidenceReport:
    observed = result.ledger.named_buyer_net_outflow
    floor_map = {
        response.operator_id: floors[response.operator_id - 1] for response in result.used_responses
    }
    allocation_check = verify_allocation_witness(aggregation, allocation, floor_map, observed)

    b1 = _gate_b1(result, aggregation)
    gates = {
        "B1": b1,
        "B2": _gate_b2(result),
        "B3": _gate_b3(result, b1),
        "B4": _gate_b4(result),
        "B5": _gate_b5(result, coverage),
    }

    statuses = [verdict.status for verdict in gates.values()]
    if FAIL_COUNTEREXAMPLE in statuses:
        status = REFUTED
    elif FAIL_CLOSED_MISSING_EVIDENCE in statuses or not allocation_check.ok:
        status = UNKNOWN
    else:
        status = CERTIFIED

    # The execution floor is a property of the ledger and its allocation witness,
    # not of the verdict: it is defined whenever the witness verifies, and it is
    # never substituted by the closed-form cover value.
    execution_floor = allocation.total_allocated if allocation_check.ok else None
    return EvidenceReport(
        gates=gates,
        allocation_check=allocation_check,
        execution_floor=execution_floor,
        observed_outflow=observed,
        status=status,
    )
