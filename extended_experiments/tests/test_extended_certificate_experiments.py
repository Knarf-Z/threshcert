from __future__ import annotations

import csv
import sys
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_extended_certificate_experiments import (  # noqa: E402
    RESISTANCE_PROFILES,
    exact_uniform_certificate,
)


def read_rows(name: str) -> list[dict[str, str]]:
    with (ROOT / "results" / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class ExtendedCertificateExperimentTests(unittest.TestCase):
    def test_scalability_rows_match_recorded_repeats(self) -> None:
        rows = read_rows("scalability_analysis.csv")
        self.assertEqual([int(row["n"]) for row in rows], [8, 10, 12, 14, 16, 18])
        self.assertEqual([int(row["subset_states"]) for row in rows], [1 << n for n in [8, 10, 12, 14, 16, 18]])
        self.assertTrue(all(int(row["runs"]) == 10 for row in rows))
        medians = [float(row["median_seconds"]) for row in rows]
        self.assertTrue(all(left < right for left, right in zip(medians, medians[1:])))
        self.assertEqual(rows[-1]["median_seconds"], "7.495092400")

    def test_cost_models_separate_sorting_from_subset_enumeration(self) -> None:
        rows = read_rows("certificate_cost_models.csv")
        self.assertEqual([int(row["n"]) for row in rows], [7, 14, 28, 56, 112, 224, 448])
        for row in rows:
            n = int(row["n"])
            self.assertEqual(int(row["generic_subset_states"]), 1 << n)
            self.assertLess(
                int(row["uniform_lower_tail_sort_upper_bound"]),
                int(row["generic_subset_states"]),
            )

    def test_parameter_sensitivity_monotonicities(self) -> None:
        rows = read_rows("parameter_sensitivity.csv")
        self.assertEqual(len(rows), 48)
        grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[(row["profile"], int(row["initial_exposure_shares"]))].append(row)
            resistances = RESISTANCE_PROFILES[row["profile"]]
            required = int(row["required_additional_shares"])
            self.assertEqual(
                int(row["exact_certificate"]),
                exact_uniform_certificate(resistances, required),
            )
        for profile in RESISTANCE_PROFILES:
            for exposure in (0, 1, 2):
                values = [
                    int(row["exact_certificate"])
                    for row in sorted(
                        grouped[(profile, exposure)],
                        key=lambda item: int(item["threshold_shares"]),
                    )
                ]
                self.assertTrue(all(left <= right for left, right in zip(values, values[1:])))

        by_threshold: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_threshold[(row["profile"], int(row["threshold_shares"]))].append(row)
        for group in by_threshold.values():
            values = [
                int(row["exact_certificate"])
                for row in sorted(group, key=lambda item: int(item["initial_exposure_shares"]))
            ]
            self.assertTrue(all(left >= right for left, right in zip(values, values[1:])))

    def test_simple_baseline_validity_and_tightness(self) -> None:
        rows = read_rows("baseline_comparison.csv")
        self.assertEqual(len(rows), 64)
        grouped: dict[tuple[str, int], dict[str, dict[str, str]]] = defaultdict(dict)
        for row in rows:
            grouped[(row["profile"], int(row["required_shares"]))][row["method"]] = row
        for methods in grouped.values():
            exact = float(methods["exact_lower_tail"]["value"])
            self.assertEqual(float(methods["public_only"]["value"]), 0.0)
            self.assertLessEqual(float(methods["minimum_member_floor"]["value"]), exact)
            self.assertGreaterEqual(float(methods["mean_resistance_heuristic"]["value"]), exact)
            self.assertEqual(methods["mean_resistance_heuristic"]["certified_lower_bound"], "false")
            self.assertEqual(methods["exact_lower_tail"]["certified_lower_bound"], "true")


if __name__ == "__main__":
    unittest.main()
