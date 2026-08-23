"""Regression tests for the v3 fail-closed catalog and run classification."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.certificate import catalog_certificate  # noqa: E402


spec = importlib.util.spec_from_file_location("run_two_host", ROOT / "scripts" / "run_two_host.py")
assert spec is not None and spec.loader is not None
run_two_host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_two_host)


class FailClosedCatalogTests(unittest.TestCase):
    def test_catalog_certificate_rejects_missing_route_floor(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete route catalog"):
            catalog_certificate([2, None, 10])

    def test_incomplete_catalog_has_no_numeric_certificate(self) -> None:
        routes = [
            {
                "route_id": "R-0000",
                "coalition": [1, 2, 3, 4],
                "order": [1, 2, 3, 4],
                "execution_floor": 10,
                "observed_outflow": 10,
                "catalog_eligible": True,
            },
            {
                "route_id": "R-0001",
                "coalition": [1, 2, 3, 4],
                "order": [1, 2, 4, 3],
                "execution_floor": 6,
                "observed_outflow": 6,
                "catalog_eligible": False,
            },
        ]
        summary = run_two_host._summarise_catalog(routes, {(1, 2, 3, 4), (1, 2, 4, 3)})
        self.assertFalse(summary["complete_for_declared_first_four_route_grammar"])
        self.assertIsNone(summary["catalog_certificate"])
        self.assertIsNone(summary["observed_minimum"])
        self.assertEqual(summary["minimizing_route_ids"], [])
        self.assertEqual(summary["coalition_floors"], {})
        self.assertEqual(summary["incomplete_route_ids"], ["R-0001"])

    def test_complete_catalog_is_priced(self) -> None:
        routes = [
            {
                "route_id": "R-0000",
                "coalition": [1, 2, 3, 4],
                "order": [1, 2, 3, 4],
                "execution_floor": 10,
                "observed_outflow": 10,
                "catalog_eligible": True,
            },
            {
                "route_id": "R-0001",
                "coalition": [2, 4, 6, 7],
                "order": [2, 4, 6, 7],
                "execution_floor": 19,
                "observed_outflow": 19,
                "catalog_eligible": True,
            },
        ]
        summary = run_two_host._summarise_catalog(routes, {(1, 2, 3, 4), (2, 4, 6, 7)})
        self.assertTrue(summary["complete_for_declared_first_four_route_grammar"])
        self.assertEqual(summary["catalog_certificate"], 10)
        self.assertEqual(summary["observed_minimum"], 10)
        self.assertEqual(summary["minimizing_route_ids"], ["R-0000"])

    def test_failed_checks_cannot_be_classified_as_certified(self) -> None:
        failed, run_class = run_two_host._classify_run(
            {"baseline_certified": False, "host_separation": True},
            cross_host_required=True,
            catalog_requested=True,
        )
        self.assertEqual(failed, ["baseline_certified"])
        self.assertEqual(run_class, "NETWORK_OR_CONFIGURATION_FAILURE")


if __name__ == "__main__":
    unittest.main()
