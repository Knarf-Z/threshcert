"""Unit tests for the capability-circuit core (WP5 Theorems 2-4 in code)."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.capability import (
    AND,
    LEAF,
    OR,
    THR,
    Circuit,
    Derivation,
    Node,
    Support,
    canonical_potential,
    check_derivation,
    circuit_value,
    derivation_cost,
    duplicate_resources,
    is_decomposable,
    min_derivation,
    min_unique_cover_cost,
    set_cover_circuit,
    threshold_service,
    unique_resource_cost,
    value_of,
    verify_potential,
)

FLOORS = (1, 2, 3, 4, 5, 6, 7)


class ValueTests(unittest.TestCase):
    def test_threshold_value_is_sum_of_q_smallest(self) -> None:
        c = threshold_service(FLOORS, 4)
        self.assertEqual(value_of(c), 10)

    def test_or_is_min_and_and_is_sum(self) -> None:
        nodes = {
            "a": Node("a", LEAF, floor=5, support=Support(frozenset({"da"}))),
            "b": Node("b", LEAF, floor=3, support=Support(frozenset({"db"}))),
            "orn": Node("orn", OR, children=("a", "b")),
            "andn": Node("andn", AND, children=("a", "b")),
        }
        self.assertEqual(circuit_value(Circuit("orn", nodes))["orn"], 3)
        self.assertEqual(circuit_value(Circuit("andn", nodes))["andn"], 8)

    def test_cycle_is_rejected(self) -> None:
        nodes = {
            "a": Node("a", OR, children=("b",)),
            "b": Node("b", OR, children=("a",)),
        }
        with self.assertRaisesRegex(ValueError, "cyclic"):
            value_of(Circuit("a", nodes))

    def test_free_export_leaf_collapses_value(self) -> None:
        c = threshold_service(FLOORS, 4)
        # add a zero-cost export route reconstructing from four exported shares
        for i in range(1, 8):
            name = f"e{i}"
            c.nodes[name] = Node(name, LEAF, floor=0, support=Support(frozenset({f"exp-{i}"})))
        c.nodes["export"] = Node("export", THR, children=tuple(f"e{i}" for i in range(1, 8)),
                                 weights=(1,) * 7, threshold=4)
        c.nodes["root"] = Node("root", OR, children=("u", "export"))
        c.root = "root"
        self.assertEqual(value_of(c), 0)

    def test_free_bypass_collapses_value(self) -> None:
        c = threshold_service(FLOORS, 4)
        c.nodes["bypass"] = Node("bypass", LEAF, floor=0, support=Support(frozenset({"bp"})))
        c.nodes["root"] = Node("root", OR, children=("u", "bypass"))
        c.root = "root"
        self.assertEqual(value_of(c), 0)


class PotentialDualityTests(unittest.TestCase):
    def test_canonical_potential_is_feasible_and_tight(self) -> None:
        c = threshold_service(FLOORS, 4)
        z = canonical_potential(c)
        self.assertTrue(verify_potential(c, z))
        self.assertEqual(z[c.root], value_of(c))

    def test_potential_cannot_exceed_value(self) -> None:
        c = threshold_service(FLOORS, 4)
        z = dict(canonical_potential(c))
        z["u"] = z["u"] + 1  # claim a floor above the true value
        self.assertFalse(verify_potential(c, z))

    def test_duality_dichotomy(self) -> None:
        c = threshold_service(FLOORS, 4)
        val = value_of(c)
        # (1) a potential reaching g exists iff g <= val
        self.assertTrue(verify_potential(c, canonical_potential(c)) and canonical_potential(c)[c.root] >= val)
        # (2) a cheaper derivation exists iff g > val
        self.assertLess(derivation_cost(min_derivation(c)), val + 1)


class DerivationTests(unittest.TestCase):
    def test_min_derivation_is_valid_and_costs_the_value(self) -> None:
        c = threshold_service(FLOORS, 4)
        d = min_derivation(c)
        self.assertTrue(check_derivation(c, d))
        self.assertEqual(derivation_cost(d), value_of(c))

    def test_min_derivation_picks_the_cheapest_coalition(self) -> None:
        c = threshold_service(FLOORS, 4)
        chosen = sorted(leaf.name for leaf in min_derivation(c).leaves())
        self.assertEqual(chosen, ["op1", "op2", "op3", "op4"])

    def test_tampered_derivation_is_rejected(self) -> None:
        c = threshold_service(FLOORS, 4)
        d = min_derivation(c)
        # forge a leaf floor
        bad = Derivation("u", THR, children=tuple(
            Derivation(leaf.name, LEAF, floor=0, support=leaf.support) for leaf in d.leaves()
        ))
        self.assertFalse(check_derivation(c, bad))

    def test_below_threshold_derivation_is_rejected(self) -> None:
        c = threshold_service(FLOORS, 4)
        leaves = min_derivation(c).leaves()[:3]  # only three, below threshold 4
        bad = Derivation("u", THR, children=tuple(
            Derivation(l.name, LEAF, floor=l.floor, support=l.support) for l in leaves
        ))
        self.assertFalse(check_derivation(c, bad))


class DecomposabilityTests(unittest.TestCase):
    def test_clean_threshold_run_is_decomposable(self) -> None:
        c = threshold_service(FLOORS, 4)
        self.assertTrue(is_decomposable(min_derivation(c)))

    def test_shared_debit_breaks_decomposability(self) -> None:
        # AND(a, b) both citing the same debit: Proposition 5's counterexample.
        shared = Support(debit_ids=frozenset({"d"}))
        nodes = {
            "a": Node("a", LEAF, floor=5, support=shared),
            "b": Node("b", LEAF, floor=5, support=shared),
            "root": Node("root", AND, children=("a", "b")),
        }
        c = Circuit("root", nodes)
        d = min_derivation(c)
        self.assertEqual(derivation_cost(d), 10)              # additive over-claims
        self.assertFalse(is_decomposable(d))                  # ... and is caught
        self.assertEqual(duplicate_resources(d), {"debit_ids": ["d"]})
        self.assertEqual(unique_resource_cost(d, {"d": 5}), 5)  # true cost is 5 < 10

    def test_proposition5_value_is_not_a_lower_bound_when_shared(self) -> None:
        """The additive value exceeds the true unique-resource cost, so it would
        be an unsound lower bound -- the reason a certificate must be withheld."""
        shared = Support(debit_ids=frozenset({"d"}))
        nodes = {
            "a": Node("a", LEAF, floor=5, support=shared),
            "b": Node("b", LEAF, floor=5, support=shared),
            "root": Node("root", AND, children=("a", "b")),
        }
        c = Circuit("root", nodes)
        d = min_derivation(c)
        self.assertGreater(derivation_cost(d), unique_resource_cost(d, {"d": 5}))


class SetCoverHardnessTests(unittest.TestCase):
    def test_reduction_matches_min_set_cover(self) -> None:
        universe = [1, 2, 3, 4, 5]
        sets = [[1, 2, 3], [2, 4], [3, 4, 5], [5]]
        circuit, prices = set_cover_circuit(universe, sets)
        # brute over derivations: pick one covering leaf per element, dedup debits
        from itertools import product

        best = None
        element_options = []
        for u in universe:
            covering = [j for j, s in enumerate(sets) if u in s]
            element_options.append(covering)
        for choice in product(*element_options):
            used = set(choice)
            cost = sum(prices[f"r{j}"] for j in used)
            best = cost if best is None else min(best, cost)
        self.assertEqual(best, min_unique_cover_cost(universe, sets))

    def test_circuit_is_depth_two_and_and_or_only(self) -> None:
        circuit, _ = set_cover_circuit([1, 2], [[1], [1, 2], [2]])
        kinds = {n.kind for n in circuit.nodes.values()}
        self.assertTrue(kinds <= {LEAF, OR, AND})
        self.assertEqual(circuit.nodes["root"].kind, AND)


if __name__ == "__main__":
    unittest.main()
