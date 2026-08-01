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
    counterfactual_vectors_for_roles,
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
            "deterministic equal-cost weighted counterfactual on a seven-member four-of-seven threshold",
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
            branches["resistance_only_threshold_cover"]["certificate"], "2"
        )
        self.assertEqual(
            branches["resistance_only_threshold_cover"]["cover"], [0, 1]
        )
        self.assertEqual(branches["activation_cover"]["certificate"], "4")
        self.assertEqual(branches["activation_cover"]["witness"], [5, 6, 0, 1])
        self.assertTrue(
            branches["activation_cover"]["activation_certificate_emitted"]
        )
        fallback = branches["activation_gate_rejected_robust_fallback"]
        self.assertEqual(fallback["certificate"], "2")
        self.assertEqual(
            fallback["selected_branch"], "ROBUST_THRESHOLD_COVER_FALLBACK"
        )
        self.assertFalse(fallback["activation_certificate_emitted"])

    def test_all_role_assignments_return_tc_2_and_ac_4(self) -> None:
        geometry = self.fixture["production_geometry"]
        seen: list[tuple[tuple[int, int], tuple[int, int]]] = []
        universe = set(range(7))
        for prerequisites in combinations(range(7), 2):
            remaining = sorted(universe - set(prerequisites))
            for cores in combinations(remaining, 2):
                weights, resistances, activations = counterfactual_vectors_for_roles(
                    prerequisites, cores, 7
                )
                solved = solve_profile(
                    weights,
                    resistances,
                    activations,
                    Fraction(geometry["threshold"]),
                    Fraction(geometry["initial_exposure"]),
                )
                self.assertEqual(
                    solved["threshold_cover"], Fraction(2), (prerequisites, cores)
                )
                self.assertEqual(
                    solved["activation_cover"], Fraction(4), (prerequisites, cores)
                )
                seen.append((prerequisites, cores))
        self.assertEqual(len(seen), 210)
        regressions = self.result["regression_checks"]
        self.assertEqual(regressions["role_assignments_checked"], 210)
        self.assertTrue(regressions["all_role_assignments_tc_2_ac_4"])

    def test_activation_gate_failures_do_not_emit_four(self) -> None:
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
            self.assertEqual(selected["certificate"], "2")
            self.assertFalse(selected["activation_certificate_emitted"])

    def test_recorded_json_matches_recomputation_and_has_portable_newlines(self) -> None:
        path = ROOT / "results" / "gnosis_counterfactual_result.json"
        recorded_bytes = path.read_bytes()
        self.assertTrue(recorded_bytes.endswith(b"\n"))
        self.assertNotIn(b"\r\n", recorded_bytes)
        self.assertEqual(json.loads(recorded_bytes), self.result)


if __name__ == "__main__":
    unittest.main()
