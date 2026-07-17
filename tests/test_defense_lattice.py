from __future__ import annotations

import sys
import unittest
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from defense_lattice import (  # noqa: E402
    coordinated_defense_values,
    decoy_fixed_family_value,
    exact_budget_maximizer,
    is_monotone,
    marginal_greedy,
    minimal_target_masks,
    mobius_transform,
    truncated_value,
    zeta_transform,
)


class DefenseLatticeTests(unittest.TestCase):
    def test_mobius_round_trip(self) -> None:
        values = [0, 1, 2, 7, 3, 8, 10, 25]
        coefficients = mobius_transform(values, 3)
        self.assertEqual(zeta_transform(coefficients, 3), values)

    def test_pure_high_order_construction(self) -> None:
        k = 4
        multiple = 7
        values = coordinated_defense_values(k, multiple)
        coefficients = mobius_transform(values, k)
        full_mask = (1 << k) - 1
        self.assertEqual(values[0], Fraction(2))
        self.assertEqual(values[full_mask], Fraction(2 * multiple))
        self.assertTrue(all(value == 0 for value in coefficients[1:full_mask]))
        self.assertEqual(coefficients[full_mask], Fraction(2 * multiple - 2))
        self.assertTrue(is_monotone(values, k))

    def test_low_order_truncation_misses_full_interaction(self) -> None:
        k = 5
        multiple = 11
        values = coordinated_defense_values(k, multiple)
        coefficients = mobius_transform(values, k)
        full_mask = (1 << k) - 1
        for order in range(1, k):
            self.assertEqual(truncated_value(coefficients, k, full_mask, order), 2)
        self.assertEqual(values[full_mask], 22)

    def test_minimal_target_masks(self) -> None:
        values = [0, 0, 0, 2, 0, 3, 4, 5]
        self.assertTrue(is_monotone(values, 3))
        self.assertEqual(set(minimal_target_masks(values, 3, 3)), {0b101, 0b110})

    def test_decoys_defeat_singleton_marginal_greedy(self) -> None:
        k = 4
        action_count, value = decoy_fixed_family_value(k, 100.0, 0.01)
        exact_mask, exact_value = exact_budget_maximizer(value, action_count, k)
        greedy_mask, greedy_value = marginal_greedy(value, action_count, k)
        self.assertEqual(exact_mask, (1 << k) - 1)
        self.assertEqual(greedy_mask >> k, (1 << k) - 1)
        self.assertEqual(exact_value, 200.0)
        self.assertLess(greedy_value, 3.0)


if __name__ == "__main__":
    unittest.main()
