"""
Independent verification of Theorem (Exact characterization under a general
family), Corollary (cardinality families make repetition redundant), and
Corollary (unbounded repetition collapses to the package floor): the
generalization of the atomic-bypass mechanism to an arbitrary certified
package family m_{B,r} -- the attacker may invoke at most r pairwise-disjoint
packages from a certified family B subset of 2^U0 (not necessarily
cardinality-bounded), each package activation-free, everything else
sequential.

Key mathematical content, not just code: for the CARDINALITY-bounded family
B_b = {P : |P| <= b}, the repetition budget r is REDUNDANT -- B_b^{+r} =
B_{r*b} exactly, so m_{B_b,r} has EXACTLY the same certificate as the
single-package m_bypass(r*b) already in atomic_bypass_hierarchy.py.
Repetition only adds new content when B is NOT simply a cardinality bound
(e.g. a fixed menu of specific certifiably-deployable package contracts).
This directly answers "why does the paper's m_bypass(b) theorem fix r=1":
for the size-bounded family, allowing r>1 uses doesn't even change the
answer from allowing one bigger package -- and if B contains every
singleton (true whenever b>=1), unlimited repetition (r towards infinity)
collapses the certificate all the way to TCR, erasing the entire hierarchy.
r=1 is the boundary at which the hierarchy stops collapsing, not an
arbitrary modeling choice.

Two independent computations of ABC_{B,r}(A0), cross-checked:

  1. `general_state_space`: memoized recursion over (acquired set, packages
     used so far), directly from the m_{B,r} mechanism definition, stopping
     at the first threshold crossing. Does not assume any particular
     package triggers first.

  2. `general_closed_form`: the theorem's closed form, minimizing over the
     r-fold disjoint-union closure of B, reusing
     `atomic_bypass_hierarchy.py`'s reduction pattern (and core.py's
     ac_formula_gamma_star) rather than a new solver.
"""
import sys, os, itertools
from functools import lru_cache
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ac_formula_gamma_star, random_instance, deterministic_seed
from atomic_bypass_hierarchy import abc_closed_form

_ZERO_TAU_CACHE = {}


def zero_tau(n):
    if n not in _ZERO_TAU_CACHE:
        _ZERO_TAU_CACHE[n] = [Fr(0)] * n
    return _ZERO_TAU_CACHE[n]


def general_state_space(w, t, A0, tau, R, families, r):
    """Ground truth for m_{B,r}: at most r pairwise-disjoint packages from
    `families` (an iterable of frozensets, each a certified atomic
    package), each activation-free; everything else sequential. Memoized
    recursion, stops at the first threshold crossing."""
    n = len(w)
    U0 = frozenset(i for i in range(n) if i not in A0)

    def weight(S):
        return sum((w[i] for i in S), Fr(0))

    families = tuple(frozenset(P) for P in families)

    @lru_cache(maxsize=None)
    def solve(acquired, packages_used):
        current = A0 | set(acquired)
        if weight(current) >= t:
            return Fr(0)
        remaining = U0 - acquired
        exposure = weight(current)
        best = None

        for i in remaining:
            if tau[i] <= exposure:
                rest = solve(acquired | frozenset((i,)), packages_used)
                if rest is not None:
                    candidate = R[i] + rest
                    if best is None or candidate < best:
                        best = candidate

        if packages_used < r:
            for P in families:
                if P & acquired or not (P <= remaining):
                    continue
                rest = solve(acquired | P, packages_used + 1)
                if rest is not None:
                    candidate = sum((R[i] for i in P), Fr(0)) + rest
                    if best is None or candidate < best:
                        best = candidate

        return best

    return solve(frozenset(), 0)


def disjoint_union_closure(families, r):
    """B^{+r}: all unions of <= r pairwise-disjoint members of `families`."""
    families = [frozenset(P) for P in families]
    closure = {frozenset()}
    frontier = {frozenset()}
    for _ in range(r):
        new_frontier = set()
        for base in frontier:
            for P in families:
                if P & base:
                    continue
                combined = base | P
                if combined not in closure:
                    closure.add(combined)
                    new_frontier.add(combined)
        frontier = new_frontier
        if not frontier:
            break
    return closure


def general_closed_form(w, t, A0, tau, R, families, r):
    """ABC_{B,r}(A0) via the closure: enumerate every P in B^{+r}, reuse
    ac_formula_gamma_star with A0|P for the sequential remainder."""
    best = None
    for P in disjoint_union_closure(families, r):
        package_cost = sum(R[i] for i in P)
        sub_A0 = A0 | P
        if sum(w[i] for i in sub_A0) >= t:
            rest = Fr(0)
        else:
            rest = ac_formula_gamma_star(w, t, sub_A0, tau, R)
        if rest is None:
            continue
        total = package_cost + rest
        if best is None or total < best:
            best = total
    return best


def random_family(rng, U0, size):
    """A small, deliberately non-cardinality-structured family: `size`
    random subsets of U0 of random (mixed) sizes."""
    U0 = list(U0)
    family = set()
    attempts = 0
    while len(family) < size and attempts < size * 20:
        attempts += 1
        k = rng.randint(1, max(1, len(U0) // 2))
        P = frozenset(rng.sample(U0, k))
        if P:
            family.add(P)
    return family


def check_general_cross_validation(
    n_values=(3, 4, 5, 6), r_values=(0, 1, 2, 3, 4), trials_per_n=40, seed_base=20260722
):
    import random as _random

    total = 0
    mismatches = []
    for n in n_values:
        for r in r_values:
            for trial in range(trials_per_n):
                seed = deterministic_seed(n, r, trial, seed_base, "genfam")
                wk = "random" if trial % 2 else "uniform"
                w, t, A0, tau, R = random_instance(n, seed, weight_kind=wk)
                U0 = [i for i in range(n) if i not in A0]
                rng = _random.Random(seed ^ 0xABCDEF)
                family = random_family(rng, U0, size=4)
                total += 1
                gt = general_state_space(w, t, A0, tau, R, family, r)
                cf = general_closed_form(w, t, A0, tau, R, family, r)
                if gt != cf:
                    mismatches.append((n, r, seed, family, gt, cf))
    return total, mismatches


def check_cardinality_family_redundancy(
    n_values=(3, 4, 5, 6, 7),
    b_values=(1, 2, 3),
    r_values=(1, 2, 3, 4),
    trials_per_n=25,
    seed_base=20260722,
):
    """Corollary: for B_b = {P : |P| <= b}, B_b^{+r} == B_{r*b}, so
    ABC_{B_b,r} == ABC_{r*b} (the single-package theorem already in the
    paper, via abc_closed_form)."""
    total = 0
    mismatches = []
    for n in n_values:
        for b in b_values:
            for r in r_values:
                for trial in range(trials_per_n):
                    seed = deterministic_seed(n, b, r, trial, seed_base, "card")
                    wk = "random" if trial % 2 else "uniform"
                    w, t, A0, tau, R = random_instance(n, seed, weight_kind=wk)
                    U0 = [i for i in range(n) if i not in A0]
                    families_b = [
                        frozenset(P)
                        for k in range(1, b + 1)
                        for P in itertools.combinations(U0, k)
                    ]
                    total += 1
                    general = general_closed_form(w, t, A0, tau, R, families_b, r)
                    single_big = abc_closed_form(w, t, A0, tau, R, min(r * b, len(U0)))
                    if general != single_big:
                        mismatches.append((n, b, r, seed, general, single_big))
    return total, mismatches


def check_full_collapse_with_singletons(
    n_values=(3, 4, 5, 6, 7, 8), trials_per_n=40, seed_base=20260722
):
    """Corollary: if B contains every singleton, unlimited repetition
    (r >= |U0|) collapses the certificate all the way to TCR."""
    total = 0
    mismatches = []
    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base, "collapse")
            wk = "random" if trial % 2 else "uniform"
            w, t, A0, tau, R = random_instance(n, seed, weight_kind=wk)
            U0 = [i for i in range(n) if i not in A0]
            total += 1
            singleton_family = [frozenset((i,)) for i in U0]
            tcr = ac_formula_gamma_star(w, t, A0, zero_tau(n), R)
            collapsed = general_closed_form(
                w, t, A0, tau, R, singleton_family, len(U0)
            )
            if collapsed != tcr:
                mismatches.append((n, seed, collapsed, tcr))
    return total, mismatches


if __name__ == "__main__":
    total, mismatches = check_general_cross_validation()
    print(f"general_family_cross_validation_tested={total}")
    print(f"general_family_mismatches={len(mismatches)}")
    if mismatches:
        print("\n!!! MISMATCH !!!")
        for m in mismatches[:5]:
            print(f"  {m}")

    total2, mismatches2 = check_cardinality_family_redundancy()
    print(f"cardinality_redundancy_tested={total2}")
    print(f"cardinality_redundancy_mismatches={len(mismatches2)}")
    if mismatches2:
        print("\n!!! MISMATCH -- repetition of a cardinality family is NOT redundant?! !!!")
        for m in mismatches2[:5]:
            print(f"  {m}")

    total3, mismatches3 = check_full_collapse_with_singletons()
    print(f"full_collapse_tested={total3}")
    print(f"full_collapse_mismatches={len(mismatches3)}")
    if mismatches3:
        print("\n!!! MISMATCH -- unlimited singleton repetition did not collapse to TCR !!!")
        for m in mismatches3[:5]:
            print(f"  {m}")

    problems = mismatches + mismatches2 + mismatches3
    if problems:
        raise SystemExit(1)
    print()
    print(
        "PASS: general_package_family_hierarchy -- no counterexample was "
        "found: the general state-space computation matched the general "
        "closed form on exotic (non-cardinality) random families "
        f"({total} instances); cardinality-bounded families confirmed "
        f"repetition r is redundant, B_b^+r = B_{{r*b}} ({total2} "
        "instances against the single-package theorem's own closed form); "
        f"and singleton-containing families confirmed unlimited repetition "
        f"collapses exactly to TCR ({total3} instances)."
    )
