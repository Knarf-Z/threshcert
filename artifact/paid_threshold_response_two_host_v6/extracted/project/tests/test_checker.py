"""Tests for the capability-certificate checker (WP5/WP6 verdicts)."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.checker import (
    CERTIFIED,
    NONDECOMPOSABLE,
    REFUTED_BY_DERIVATION,
    UNKNOWN_ALLOCATION,
    build_two_host_circuit,
    certify,
    route_compression,
    with_free_bypass,
    with_shared_debit,
)

FLOORS = (1, 2, 3, 4, 5, 6, 7)


class CheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.circuit = build_two_host_circuit(FLOORS, 4)

    def test_baseline_certifies_the_cover_with_a_verified_potential(self) -> None:
        r = certify(self.circuit, target=10)
        self.assertEqual(r.status, CERTIFIED)
        self.assertEqual(r.circuit_value, 10)
        self.assertTrue(r.potential_verified)
        self.assertTrue(r.decomposable)
        self.assertEqual(r.derivation_cost, 10)

    def test_free_bypass_refutes_the_cover(self) -> None:
        r = certify(with_free_bypass(self.circuit), target=10)
        self.assertEqual(r.status, REFUTED_BY_DERIVATION)
        self.assertEqual(r.circuit_value, 0)
        self.assertLess(r.derivation_cost, 10)

    def test_shared_debit_is_nondecomposable_not_summed(self) -> None:
        r = certify(with_shared_debit(self.circuit, 1, 2), target=10)
        self.assertEqual(r.status, NONDECOMPOSABLE)
        self.assertIn("debit_ids", r.duplicate_resources)
        self.assertEqual(r.duplicate_resources["debit_ids"], ["debit-shared"])

    def test_missing_allocation_yields_unknown(self) -> None:
        r = certify(self.circuit, allocation_ok=False, target=10)
        self.assertEqual(r.status, UNKNOWN_ALLOCATION)

    def test_compression_counts(self) -> None:
        self.assertEqual(route_compression(7, 4), {"ordered_routes": 840, "coalition_derivations": 35, "threshold_nodes": 1})


if __name__ == "__main__":
    unittest.main()
