"""Tests for the sealed-composition checker (Theorem 5 / LC0-LC7)."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.contracts import COVERAGE_NOT_ESTABLISHED, SEALED, verify_composition
from ptr_v3.service_model import MUTATIONS, baseline_manifest


class CompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = baseline_manifest()

    def test_baseline_is_sealed(self) -> None:
        report = verify_composition(self.base)
        self.assertEqual(report.status, SEALED)
        self.assertEqual(report.violations, [])

    def test_each_mutation_is_caught_and_isolates_its_condition(self) -> None:
        for name, (fn, expected_lc) in MUTATIONS.items():
            report = verify_composition(fn(self.base))
            with self.subTest(mutation=name):
                self.assertEqual(report.status, COVERAGE_NOT_ESTABLISHED)
                conditions = sorted({v["condition"] for v in report.violations})
                self.assertEqual(conditions, [expected_lc], f"{name} should isolate {expected_lc}")

    def test_all_conditions_lc0_to_lc7_have_a_mutation(self) -> None:
        covered = {lc for _, lc in MUTATIONS.values()}
        self.assertEqual(covered, {f"LC{i}" for i in range(8)})

    def test_cached_bypass_yields_a_counter_derivation(self) -> None:
        fn, _ = MUTATIONS["cached_output_bypass"]
        report = verify_composition(fn(self.base))
        self.assertIsNotNone(report.counter_derivation)
        self.assertTrue(any("undeclared" in step or "bypass" in step for step in report.counter_derivation))

    def test_root_missing_is_not_sealed(self) -> None:
        fn, _ = MUTATIONS["lc7_root_producer_missing"]
        self.assertEqual(verify_composition(fn(self.base)).status, COVERAGE_NOT_ESTABLISHED)


if __name__ == "__main__":
    unittest.main()
