from __future__ import annotations

import json
import sys
import unittest
from fractions import Fraction
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_gnosis_counterfactual import (  # noqa: E402
    counterfactual_vectors_for_seeds,
    evaluate_counterfactual,
    load_fixture,
    select_certified_branch,
    solve_profile,
)


class GnosisCounterfactualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture()
        cls.result = evaluate_counterfactual(cls.fixture)

    def test_fixture_is_bound_to_pinned_geometry_but_not_production_floors(self) -> None:
        geometry = self.result["pinned_geometry"]
        boundary = self.result["claim_boundary"]
        inputs = self.result["counterfactual_inputs"]
        self.assertEqual(geometry["archival_block_number"], 46_666_718)
        self.assertEqual(geometry["keyper_set_index"], 10)
        self.assertEqual(geometry["committee_size"], 7)
        self.assertEqual(geometry["threshold"], "4/7")
        self.assertEqual(geometry["member_count_verified"], 7)
        self.assertEqual(
            boundary["allowed_description"],
            "deterministic counterfactual check on the pinned committee geometry",
        )
        self.assertEqual(inputs["ledger"], "I_cf")
        self.assertEqual(inputs["cost_units"], "normalized cost units")
        self.assertEqual(boundary["resistance_floor_status"], "HYPOTHETICAL_NOT_MEASURED")
        self.assertTrue(boundary["positive_values_are_conditional"])
        self.assertFalse(boundary["production_validation"])
        self.assertFalse(boundary["measured_keyper_resistance"])
        self.assertFalse(boundary["new_chain_experiment"])

    def test_four_certificate_branches_and_witnesses(self) -> None:
        branches = self.result["branches"]
        self.assertEqual(branches["public_ledger"]["certificate"], "0")
        self.assertEqual(
            branches["resistance_only_threshold_cover"]["certificate"], "4"
        )
        self.assertEqual(
            branches["resistance_only_threshold_cover"]["cover"], [2, 3, 4, 5]
        )
        self.assertEqual(branches["activation_cover"]["certificate"], "10")
        self.assertEqual(branches["activation_cover"]["witness"], [0, 1, 2, 3])
        self.assertTrue(
            branches["activation_cover"]["activation_certificate_emitted"]
        )
        fallback = branches["activation_gate_rejected_robust_fallback"]
        self.assertEqual(fallback["certificate"], "4")
        self.assertEqual(
            fallback["selected_branch"], "ROBUST_THRESHOLD_COVER_FALLBACK"
        )
        self.assertFalse(fallback["activation_certificate_emitted"])

    def test_all_twenty_one_seed_positions_return_tc_4_and_ac_10(self) -> None:
        geometry = self.fixture["production_geometry"]
        weights = tuple(Fraction(value) for value in self.fixture["counterfactual_inputs"]["weights"])
        seen: list[tuple[int, int]] = []
        for seed_members in combinations(range(7), 2):
            resistances, activations = counterfactual_vectors_for_seeds(seed_members, 7)
            solved = solve_profile(
                weights,
                resistances,
                activations,
                Fraction(geometry["threshold"]),
                int(geometry["threshold_count"]),
                Fraction(geometry["initial_exposure"]),
            )
            self.assertEqual(solved["threshold_cover"], Fraction(4), seed_members)
            self.assertEqual(solved["activation_cover"], Fraction(10), seed_members)
            seen.append(seed_members)
        self.assertEqual(len(seen), 21)
        regressions = self.result["regression_checks"]
        self.assertEqual(regressions["seed_member_placements_checked"], 21)
        self.assertTrue(regressions["all_seed_placements_tc_4_ac_10"])

    def test_activation_gate_failures_do_not_emit_ten(self) -> None:
        branches = self.result["branches"]
        tc = Fraction(branches["resistance_only_threshold_cover"]["certificate"])
        ac = Fraction(branches["activation_cover"]["certificate"])
        for disabled_gate in (
            "ordered_witness_certified",
            "exposure_sufficiency_certified",
        ):
            gates = dict(self.fixture["certificate_gates"])
            gates[disabled_gate] = False
            selected = select_certified_branch(tc, ac, gates)
            self.assertEqual(
                selected["selected_branch"], "ROBUST_THRESHOLD_COVER_FALLBACK"
            )
            self.assertEqual(selected["certificate"], "4")
            self.assertFalse(selected["activation_certificate_emitted"])

    def test_recorded_json_matches_recomputation_and_has_portable_newlines(self) -> None:
        path = ROOT / "results" / "gnosis_counterfactual_result.json"
        recorded_bytes = path.read_bytes()
        self.assertTrue(recorded_bytes.endswith(b"\n"))
        self.assertNotIn(b"\r\n", recorded_bytes)
        self.assertEqual(json.loads(recorded_bytes), self.result)


if __name__ == "__main__":
    unittest.main()
