"""
Independent verification of Theorem (Exact atomic-bypass characterization)
and Lemma (the bypass is WLOG triggered first): the mechanism
m_bypass(b) that permits the sequential mechanism plus AT MOST ONE atomic,
activation-free package transaction during the entire covered attack, that
package containing at most b members in total.

Naming note: an earlier draft called this "m_batch(b)" and the certificate
"BCR_b", which reads as an ordinary per-transaction batch-size cap usable
repeatedly. That is not what this mechanism is -- the budget b bounds the
SIZE OF THE ONE atomic bypass allowed across the whole attack, not a
per-transaction cap under unlimited repeated use. (Allowing unlimited
repeated size-b packages would collapse BCR_1 to TCR immediately, destroying
the hierarchy.) Renamed throughout to ABC_b ("atomic-bypass cover", budget
b) and m_bypass(b) to say exactly what is being characterized. A
correspondingly precise statement belongs in the paper: "the attacker may
invoke at most one atomic package, of at most b members total, during the
entire covered attack."

Two independent computations of ABC_b(A0), cross-checked against each other:

  1. `abc_state_space`: works DIRECTLY from the m_bypass(b) mechanism
     definition via memoized recursion over (acquired set, package-used
     flag), stopping exactly at the first threshold crossing (returns 0 the
     moment cumulative weight reaches t) -- not an enumerate-every-subset
     construction that relies on non-negative costs and separate
     enumeration of truncated subsets to reach the right answer by a side
     argument. This is the ground truth for the WLOG lemma -- if
     package-first were not optimal, this state-space computation (which
     tries every valid order and trigger point implicitly, not just
     package-first schedules) would show it.

  2. `abc_closed_form`: the theorem's closed form,
     ABC_b(A0) = min over P subset of U0, |P|<=b, of
                 sum_{i in P} R_i + ACR_{R,tau}(A0 union P),
     computed by reusing core.py's own already-verified
     `ac_formula_gamma_star` as a subroutine (called with a bigger A0).

Also checks: ABC_0 == ACR; ABC_b == TCR for b at or above the size of an
optimal TCR-achieving set; monotonicity in b; and the paper's own
four-of-seven counterfactual curve (10, 7, 4, 4, 4, 4, 4, 4).

A real implementation bug was caught and fixed while writing the first
version of this check: `ac_formula_gamma_star` silently assumes the
model's own standing invariant w(A0) < t, and returns "infeasible" rather
than 0 if the passed-in A0 already reaches threshold on its own -- which
happens exactly when the package P is large enough to reach t by itself.
`abc_closed_form` handles that case directly instead of violating the
precondition.
"""
import sys, os, itertools
from functools import lru_cache
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ac_formula_gamma_star, random_instance, deterministic_seed

_ZERO_TAU_CACHE = {}


def zero_tau(n):
    if n not in _ZERO_TAU_CACHE:
        _ZERO_TAU_CACHE[n] = [Fr(0)] * n
    return _ZERO_TAU_CACHE[n]


def abc_closed_form(w, t, A0, tau, R, b):
    """ABC_b(A0) via the theorem's closed form: enumerate the atomic-bypass
    package P (any subset of U0 with |P|<=b), reuse ac_formula_gamma_star
    with a bigger initial-release set A0 | P for the sequential remainder
    (the "one bypass, then ordinary sequential for the rest" reduction that
    Lemma package-first-wlog justifies)."""
    n = len(w)
    U0 = [i for i in range(n) if i not in A0]
    best = None
    for k in range(0, min(b, len(U0)) + 1):
        for P in itertools.combinations(U0, k):
            Pset = frozenset(P)
            package_cost = sum(R[i] for i in P)
            sub_A0 = A0 | Pset
            # ac_formula_gamma_star silently assumes w(sub_A0) < t (the
            # model's own standing invariant on A0); when the package alone
            # already reaches threshold, handle that case directly instead
            # of violating the precondition.
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


def abc_state_space(w, t, A0, tau, R, b):
    """Ground truth, directly from the m_bypass(b) mechanism definition:
    memoized recursion over (acquired set, package-used flag), stopping
    exactly at the first threshold crossing. Does NOT assume the package
    triggers first, and does NOT rely on non-negative-cost truncation
    arguments -- every valid schedule (any interleaving, any trigger point,
    the package used or not) is implicitly explored via the two branches
    below."""
    n = len(w)
    U0 = frozenset(i for i in range(n) if i not in A0)

    def weight(S):
        return sum((w[i] for i in S), Fr(0))

    @lru_cache(maxsize=None)
    def solve(acquired, package_used):
        current = A0 | set(acquired)
        if weight(current) >= t:
            return Fr(0)

        remaining = U0 - acquired
        exposure = weight(current)
        best = None

        # Ordinary sequential acquisition of one more member.
        for i in remaining:
            if tau[i] <= exposure:
                rest = solve(acquired | frozenset((i,)), package_used)
                if rest is not None:
                    candidate = R[i] + rest
                    if best is None or candidate < best:
                        best = candidate

        # The one atomic bypass package, usable at most once, any size <= b.
        if not package_used:
            remaining_list = sorted(remaining)
            for k in range(1, min(b, len(remaining_list)) + 1):
                for P in itertools.combinations(remaining_list, k):
                    Pset = frozenset(P)
                    rest = solve(acquired | Pset, True)
                    if rest is not None:
                        candidate = sum((R[i] for i in P), Fr(0)) + rest
                        if best is None or candidate < best:
                            best = candidate

        return best

    return solve(frozenset(), False)


def check_cross_validation(
    n_values=(3, 4, 5, 6), b_values=(0, 1, 2, 3), trials_per_n=40, seed_base=20260722
):
    total = 0
    mismatches = []
    for n in n_values:
        for b in b_values:
            for trial in range(trials_per_n):
                seed = deterministic_seed(n, b, trial, seed_base)
                wk = "random" if trial % 2 else "uniform"
                w, t, A0, tau, R = random_instance(n, seed, weight_kind=wk)
                total += 1
                state_space = abc_state_space(w, t, A0, tau, R, b)
                closed = abc_closed_form(w, t, A0, tau, R, b)
                if state_space != closed:
                    mismatches.append((n, b, seed, state_space, closed))
    return total, mismatches


def check_boundaries_and_monotonicity(
    n_values=(3, 4, 5, 6, 7, 8), trials_per_n=60, seed_base=20260722
):
    total = 0
    boundary_mismatches = []
    monotonicity_violations = []
    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base, "bd")
            wk = "random" if trial % 2 else "uniform"
            w, t, A0, tau, R = random_instance(n, seed, weight_kind=wk)
            U0 = [i for i in range(n) if i not in A0]
            total += 1

            acr = ac_formula_gamma_star(w, t, A0, tau, R)
            tcr = ac_formula_gamma_star(w, t, A0, zero_tau(n), R)
            abc0 = abc_closed_form(w, t, A0, tau, R, 0)
            abc_full = abc_closed_form(w, t, A0, tau, R, len(U0))
            if abc0 != acr:
                boundary_mismatches.append((n, seed, "b=0 vs ACR", abc0, acr))
            if abc_full != tcr:
                boundary_mismatches.append((n, seed, "b=|U0| vs TCR", abc_full, tcr))

            prev = abc0
            for b in range(1, len(U0) + 1):
                cur = abc_closed_form(w, t, A0, tau, R, b)
                if not (cur is None and prev is None) and not (
                    cur is not None and (prev is None or cur <= prev)
                ):
                    monotonicity_violations.append((n, seed, b, prev, cur))
                prev = cur

    return total, boundary_mismatches, monotonicity_violations


def check_shutter_counterfactual_curve():
    """The paper's own pinned four-of-seven counterfactual ledger
    (Section 7.2): members {0,1} have (R,tau)=(4,0), members {2..6} have
    (R,tau)=(1,2/7)."""
    n = 7
    w = [Fr(1, 7)] * n
    t = Fr(4, 7)
    A0 = frozenset()
    R = [Fr(4), Fr(4), Fr(1), Fr(1), Fr(1), Fr(1), Fr(1)]
    tau = [Fr(0), Fr(0), Fr(2, 7), Fr(2, 7), Fr(2, 7), Fr(2, 7), Fr(2, 7)]

    curve = {}
    for b in range(0, n + 1):
        curve[b] = abc_closed_form(w, t, A0, tau, R, b)
    return curve


if __name__ == "__main__":
    total, mismatches = check_cross_validation()
    print(f"cross_validation_instances_tested={total}")
    print(f"cross_validation_mismatches={len(mismatches)}")
    if mismatches:
        print("\n!!! MISMATCH -- closed form disagrees with the state-space ground truth !!!")
        for m in mismatches[:5]:
            print(f"  {m}")

    b_total, boundary_mismatches, monotonicity_violations = (
        check_boundaries_and_monotonicity()
    )
    print(f"boundary_monotonicity_instances_tested={b_total}")
    print(f"boundary_mismatches={len(boundary_mismatches)}")
    print(f"monotonicity_violations={len(monotonicity_violations)}")
    if boundary_mismatches:
        for m in boundary_mismatches[:5]:
            print(f"  {m}")
    if monotonicity_violations:
        for m in monotonicity_violations[:5]:
            print(f"  {m}")

    curve = check_shutter_counterfactual_curve()
    print("four_of_seven_counterfactual_ABC_curve:")
    for b in sorted(curve):
        print(f"  ABC_{b} = {curve[b]}")
    expected_curve = {0: 10, 1: 7, 2: 4, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4}
    curve_mismatch = [
        b for b in expected_curve if curve.get(b) != Fr(expected_curve[b])
    ]

    all_problems = mismatches + boundary_mismatches + monotonicity_violations + curve_mismatch
    if all_problems:
        print("\n!!! DISCREPANCY FOUND !!!")
        raise SystemExit(1)

    print()
    print(
        "PASS: atomic_bypass_hierarchy -- no counterexample was found in the "
        "tested instances: the closed form matched the independent "
        "state-space computation on every one of "
        f"{total + b_total} random instances, ABC_0=ACR and "
        "ABC_{|U0|}=TCR exactly, ABC_b was monotone non-increasing in b, "
        "and the four-of-seven counterfactual curve matched the "
        "hand-computed 10, 7, 4, 4, 4, 4, 4, 4 exactly. The package-first "
        "property (Lemma package-first-wlog) is established analytically "
        "by the exchange argument in the paper's proof, not by these "
        "tests -- the state-space ground truth above does not assume it, "
        "so agreement with the closed form is evidence for, not a proof "
        "of, the lemma."
    )
