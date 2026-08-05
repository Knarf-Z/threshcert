from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_exp.certificate import (  # noqa: E402
    brute_force_weighted,
    catalog_certificate,
    theory_cover,
    uniform_positive_count,
    weighted_dp,
)


class CertificateTests(unittest.TestCase):
    def test_uniform_closed_form(self) -> None:
        self.assertEqual(theory_cover([1, 2, 3, 4, 5, 6, 7], 4), 10)
        self.assertFalse(uniform_positive_count([1, 1, 1, 0, 0, 0, 0], 4))
        self.assertTrue(uniform_positive_count([1, 1, 1, 1, 0, 0, 0], 4))

    def test_catalog_certificate_is_a_minimum_not_a_formula(self) -> None:
        self.assertEqual(catalog_certificate([22, 10, 13, 19]), 10)
        self.assertEqual(catalog_certificate([22, 19]), 19)
        with self.assertRaises(ValueError):
            catalog_certificate([None, None])

    def test_weighted_dp(self) -> None:
        weights = [3, 2, 2, 1, 1, 1, 1]
        prices = [5, 2, 3, 1, 1, 4, 6]
        brute, coalition = brute_force_weighted(weights, prices, 6)
        self.assertEqual(weighted_dp(weights, prices, 6), brute)
        self.assertEqual(brute, 7)
        self.assertEqual(list(coalition), [2, 3, 4, 5])

    def test_weighted_dp_matches_bruteforce_on_random_instances(self) -> None:
        import random

        rng = random.Random(1234)
        for _ in range(200):
            n = rng.randint(2, 8)
            weights = [rng.randint(1, 6) for _ in range(n)]
            prices = [rng.randint(0, 9) for _ in range(n)]
            threshold = rng.randint(1, sum(weights))
            brute, _ = brute_force_weighted(weights, prices, threshold)
            self.assertEqual(weighted_dp(weights, prices, threshold), brute)


if __name__ == "__main__":
    unittest.main()
