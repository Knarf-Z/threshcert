"""
Random cross-validation of Theorem (exact-activation-cover-frontier):
    Gamma*(A0)  ==  min_{S in T+(A0)} sum_{i in S} R_i
by comparing the brute-force sequential-search definition against the
independent subset/canonical-order (AC) formula, on many random small
instances -- not just the paper's own hand-picked examples.
"""
import sys, os
from fractions import Fraction as Fr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import brute_force_gamma_star, ac_formula_gamma_star, random_instance

def run(n_values=(3, 4, 5, 6, 7, 8), trials_per_n=60, weight_kinds=("uniform", "random")):
    total = 0
    mismatches = []
    for n in n_values:
        for wk in weight_kinds:
            for trial in range(trials_per_n):
                seed = hash((n, wk, trial)) & 0xffffffff
                w, t, A0, tau, R = random_instance(n, seed, weight_kind=wk)
                bf = brute_force_gamma_star(w, t, A0, tau, R)
                ac = ac_formula_gamma_star(w, t, A0, tau, R)
                total += 1
                if bf != ac:
                    mismatches.append((n, wk, seed, w, t, A0, tau, R, bf, ac))
    return total, mismatches


def edge_cases():
    """Five hand-picked instances the random generator is unlikely to hit by
    chance: an all-zero activation vector, a tied activation vector, some
    zero-resistance members, an A0 just short of the threshold, and an
    activation vector that admits no first acquisition at all (infeasible)."""

    cases = []

    # All-zero tau: activation never constrains acquisition order.
    cases.append(
        (
            "all_zero_tau",
            [Fr(1, 4)] * 4,
            Fr(1, 2),
            set(),
            [Fr(0)] * 4,
            [Fr(3), Fr(1), Fr(4), Fr(1)],
        )
    )

    # Tied tau: several members become buildable at the same exposure level,
    # exercising the canonical nondecreasing-tau tie-break.
    cases.append(
        (
            "tied_tau",
            [Fr(1, 4)] * 4,
            Fr(3, 4),
            set(),
            [Fr(0), Fr(1, 4), Fr(1, 4), Fr(1, 4)],
            [Fr(1), Fr(5), Fr(2), Fr(4)],
        )
    )

    # Zero-resistance members: free acquisitions should be used first.
    cases.append(
        (
            "zero_resistance_members",
            [Fr(1, 4)] * 4,
            Fr(1, 2),
            set(),
            [Fr(0)] * 4,
            [Fr(0), Fr(0), Fr(3), Fr(5)],
        )
    )

    # A0 just short of the threshold: only a small remaining margin to close.
    cases.append(
        (
            "near_threshold_A0",
            [Fr(1, 5)] * 5,
            Fr(41, 100),
            {0, 1},
            [Fr(0)] * 5,
            [Fr(10), Fr(10), Fr(3), Fr(7), Fr(2)],
        )
    )

    # Infeasible: every tau_i > 0, so no member can ever be acquired first
    # from an empty A0 (starting exposure 0 never reaches any tau_i).
    cases.append(
        (
            "infeasible_no_first_move",
            [Fr(1, 3)] * 3,
            Fr(1, 2),
            set(),
            [Fr(1, 3), Fr(1, 3), Fr(1, 3)],
            [Fr(1), Fr(2), Fr(3)],
        )
    )

    return cases


def run_edge_cases():
    total = 0
    mismatches = []
    for name, w, t, A0, tau, R in edge_cases():
        bf = brute_force_gamma_star(w, t, A0, tau, R)
        ac = ac_formula_gamma_star(w, t, A0, tau, R)
        total += 1
        if bf != ac:
            mismatches.append((name, w, t, A0, tau, R, bf, ac))
    return total, mismatches


if __name__ == "__main__":
    total, mismatches = run()
    edge_total, edge_mismatches = run_edge_cases()
    total += edge_total
    mismatches += edge_mismatches
    print(f"Total random instances tested: {total - edge_total}")
    print(f"Edge cases tested: {edge_total}")
    print(f"Total instances tested: {total}")
    print(f"Mismatches (brute-force sequence search vs AC-formula solver): {len(mismatches)}")
    if mismatches:
        print("\n!!! DISCREPANCY FOUND -- first 5 shown !!!")
        for m in mismatches[:5]:
            print(f"  {m}")
    else:
        print("PASS: brute-force sequential search and the (AC) set-based formula")
        print("agree on every tested instance (uniform and non-uniform weights,")
        print("n=3..8, with and without nonempty A0) and on all 5 hand-picked")
        print("edge cases (all-zero tau, tied tau, zero-resistance members,")
        print("near-threshold A0, and an infeasible instance).")
