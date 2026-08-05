from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ptr_exp.crypto import ThresholdKeySet  # noqa: E402
from ptr_exp.evidence import (  # noqa: E402
    CERTIFIED,
    FAIL_CLOSED_MISSING_EVIDENCE,
    FAIL_COUNTEREXAMPLE,
    NOT_APPLICABLE,
    PASS,
    REFUTED,
    UNKNOWN,
    evaluate_execution,
)
from ptr_exp.protocol import (  # noqa: E402
    ThresholdResponseService,
    build_aggregation_witness,
    build_allocation_witness,
    build_coverage_evidence,
)

FLOORS = [1, 2, 3, 4, 5, 6, 7]
CHEAPEST = [1, 2, 3, 4]


def _service() -> ThresholdResponseService:
    keyset = ThresholdKeySet.generate(7, 4, seed=7)
    return ThresholdResponseService(keyset, FLOORS)


def _run(service, *, order_id, coverage="PROVED", **kwargs):
    result = service.execute(CHEAPEST, order_id=order_id, buyer="b", resource="r", seed=5, **kwargs)
    aggregation = build_aggregation_witness(result)
    allocation = build_allocation_witness(result, aggregation)
    evidence = build_coverage_evidence(result, status=coverage, committee_size=7)
    return result, evaluate_execution(result, aggregation, allocation, evidence, FLOORS)


class GateDiagonalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _service()

    def test_baseline_certifies_with_ledger_derived_floor(self) -> None:
        _, report = _run(self.service, order_id="t-baseline")
        self.assertEqual(report.status, CERTIFIED)
        self.assertEqual(report.execution_floor, 10)
        self.assertEqual(report.observed_outflow, 10)
        self.assertTrue(all(v.status == PASS for v in report.gates.values()))

    def test_wrong_buyer_refutes_b1_only_and_makes_b3_vacuous(self) -> None:
        _, report = _run(self.service, order_id="t-b1", ablation="wrong_buyer")
        self.assertEqual(report.gates["B1"].status, FAIL_COUNTEREXAMPLE)
        self.assertEqual(report.gates["B3"].status, NOT_APPLICABLE)
        for gate in ("B2", "B4", "B5"):
            self.assertEqual(report.gates[gate].status, PASS, gate)
        self.assertEqual(report.status, REFUTED)

    def test_sponsor_funding_refutes_b2_only(self) -> None:
        _, report = _run(self.service, order_id="t-b2", deposit_source="sponsor")
        self.assertEqual(report.gates["B2"].status, FAIL_COUNTEREXAMPLE)
        for gate in ("B1", "B3", "B4", "B5"):
            self.assertEqual(report.gates[gate].status, PASS, gate)

    def test_early_release_refutes_b3_only(self) -> None:
        _, report = _run(self.service, order_id="t-b3", ablation="early_release")
        self.assertEqual(report.gates["B3"].status, FAIL_COUNTEREXAMPLE)
        for gate in ("B1", "B2", "B4", "B5"):
            self.assertEqual(report.gates[gate].status, PASS, gate)

    def test_reimbursement_refutes_b4_only(self) -> None:
        _, report = _run(self.service, order_id="t-b4", ablation="reimbursement")
        self.assertEqual(report.gates["B4"].status, FAIL_COUNTEREXAMPLE)
        for gate in ("B1", "B2", "B3", "B5"):
            self.assertEqual(report.gates[gate].status, PASS, gate)

    def test_bypass_refutes_b5_only(self) -> None:
        _, report = _run(self.service, order_id="t-b5", ablation="bypass", coverage="REFUTED")
        self.assertEqual(report.gates["B5"].status, FAIL_COUNTEREXAMPLE)
        for gate in ("B1", "B2", "B3", "B4"):
            self.assertEqual(report.gates[gate].status, PASS, gate)


class VerdictSeparationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _service()

    def test_missing_coverage_is_unknown_not_refuted(self) -> None:
        _, report = _run(self.service, order_id="t-unknown", coverage="UNKNOWN")
        self.assertEqual(report.gates["B5"].status, FAIL_CLOSED_MISSING_EVIDENCE)
        self.assertEqual(report.status, UNKNOWN)

    def test_missing_ordering_evidence_is_unknown(self) -> None:
        _, report = _run(self.service, order_id="t-untimed", ablation="untimed")
        self.assertEqual(report.gates["B3"].status, FAIL_CLOSED_MISSING_EVIDENCE)
        self.assertEqual(report.status, UNKNOWN)

    def test_explicit_bypass_trace_is_refuted(self) -> None:
        _, report = _run(self.service, order_id="t-refuted", ablation="bypass", coverage="REFUTED")
        self.assertEqual(report.status, REFUTED)
        self.assertIsNotNone(report.gates["B5"].witness)


class NoCoverSubstitutionTest(unittest.TestCase):
    def test_expensive_coalition_floor_is_not_the_cover_value(self) -> None:
        service = _service()
        result = service.execute(
            [4, 5, 6, 7], order_id="t-dear", buyer="b", resource="r", seed=11
        )
        aggregation = build_aggregation_witness(result)
        allocation = build_allocation_witness(result, aggregation)
        coverage = build_coverage_evidence(result, committee_size=7)
        report = evaluate_execution(result, aggregation, allocation, coverage, FLOORS)
        self.assertEqual(report.status, CERTIFIED)
        self.assertEqual(report.execution_floor, 22)
        self.assertEqual(report.observed_outflow, 22)
        self.assertNotEqual(report.execution_floor, 10)


if __name__ == "__main__":
    unittest.main()
