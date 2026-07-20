from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_generalized_committee_sweep import (  # noqa: E402
    COMMITTEE_SHAPES,
    truncated_values_by_order,
    run_shape,
)
from defense_lattice import mobius_transform, zeta_transform  # noqa: E402


class GeneralizedCommitteeSweepTests(unittest.TestCase):
    def test_truncated_values_by_order_matches_full_zeta_at_highest_order(self) -> None:
        n = 5
        values = [float(mask) for mask in range(1 << n)]
        coefficients = mobius_transform(list(values), n)
        truncated = truncated_values_by_order(coefficients, n, (1, 2, n))
        self.assertEqual(truncated[n], zeta_transform(coefficients, n))

    def test_every_committee_shape_is_monotone_with_unit_budget_one_greedy(self) -> None:
        for n, q in COMMITTEE_SHAPES:
            mobius_rows, allocation_rows = run_shape(n, q)
            self.assertTrue(
                all(row[3] for row in mobius_rows),
                f"monotonicity failed for shape {n}-of-{q}",
            )
            budget_one_ratios = [row[7] for row in allocation_rows if row[3] == 1]
            self.assertTrue(
                all(ratio == 1.0 for ratio in budget_one_ratios),
                f"budget-one greedy was not exact for shape {n}-of-{q}",
            )


if __name__ == "__main__":
    unittest.main()
