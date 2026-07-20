#!/usr/bin/env python3
"""Independent verification of the Replacement-hull characterization theorem.

`main_text.tex`/`appendix_route_b.tex` are not present on this machine (see
`README.md`'s honest-limitations note); this theorem's statement was supplied
directly by the user instead:

    Theorem (Replacement-hull characterization). Assume V_x and C_x are
    finite and R_{i,x} != empty. Then

        A_i^eps(C,x) = min_{lambda >= 0} { eps * sum_Q lambda_Q
                        + sum_v [Q_{C,x}(v) - sum_Q lambda_Q Q(v)]_+ }

    Equivalently,

        A_i^eps(C,x) = min{ 1, inf_{s>0, Q in conv(R_{i,x})}
                        (s*eps + sum_v [Q_{C,x}(v) - s*Q(v)]_+) }

    In particular,

        Q_{C,x} not in conv(R_{i,x})
            <=> exists phi_i: E_{Q_{C,x}}[phi_i] > sup_{Q in R_{i,x}} E_Q[phi_i].

This module checks two things on small finite instances, using only the
Python standard library and exact `fractions.Fraction` arithmetic:

1. The primal (lambda) formula and the equivalent (s, Q in conv(R)) formula
   give the same value of A_i^eps(C,x), on random instances and several eps.
   Both are solved exactly as linear programs (brute-force vertex
   enumeration -- correct but exponential, intended for the small instance
   sizes used here, exactly like `core.py`'s `brute_force_gamma_star`).
   Formula 2 has a continuous parameter s; rather than a grid search over s
   (which only gives an approximate, tolerance-based check), this module
   extracts s* = sum(lambda*) from formula 1's own optimal lambda* and
   re-solves formula 2's inner simplex-constrained problem at that exact s*
   via a completely separate linear program. If the two formulas describe
   the same optimum, this must reproduce formula 1's value exactly (an exact
   Fraction equality, not an approximate one) -- a non-tautological check,
   since the inner LP is solved independently rather than by reusing
   lambda*'s implied mu.
2. The separation corollary, on hand-picked constructive instances where a
   separating functional can be exhibited and checked directly rather than
   searched for -- the general case would need a genuine separating-hyperplane
   solver, which this module does not implement (an honest limitation, noted
   in `README.md` alongside the others already documented there).
"""
from __future__ import annotations

import random
import time
from fractions import Fraction as Fr
from itertools import combinations


# ---------------------------------------------------------------------------
# Small exact LP solver: minimize c . x subject to (a . x <= b) for each row,
# and x >= 0. Brute-force vertex enumeration with exact Fraction arithmetic.
# Small instances only (this module keeps n, len(rows) under ~10).
# ---------------------------------------------------------------------------


def solve_square_system(matrix: list[list[Fr]], rhs: list[Fr]) -> list[Fr] | None:
    n = len(matrix)
    augmented = [list(row) + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot_row = next(
            (r for r in range(col, n) if augmented[r][col] != 0), None
        )
        if pivot_row is None:
            return None
        augmented[col], augmented[pivot_row] = augmented[pivot_row], augmented[col]
        pivot = augmented[col][col]
        augmented[col] = [value / pivot for value in augmented[col]]
        for r in range(n):
            if r != col and augmented[r][col] != 0:
                factor = augmented[r][col]
                augmented[r] = [
                    augmented[r][k] - factor * augmented[col][k] for k in range(n + 1)
                ]
    return [augmented[i][n] for i in range(n)]


def min_lp(
    c: list[Fr], rows: list[tuple[tuple[Fr, ...], Fr]], n: int
) -> tuple[Fr | None, list[Fr] | None]:
    """Minimize c . x s.t. a . x <= b for (a, b) in rows, and x >= 0.

    Assumes a finite optimum exists (true for every LP built in this module,
    since c >= 0 componentwise and x=0-ish points are always feasible).
    """

    all_rows = list(rows)
    for i in range(n):
        neg_e = [Fr(0)] * n
        neg_e[i] = Fr(-1)
        all_rows.append((tuple(neg_e), Fr(0)))

    best_value: Fr | None = None
    best_x: list[Fr] | None = None
    for tight in combinations(range(len(all_rows)), n):
        matrix = [list(all_rows[i][0]) for i in tight]
        rhs = [all_rows[i][1] for i in tight]
        x = solve_square_system(matrix, rhs)
        if x is None:
            continue
        if any(
            sum(a[j] * x[j] for j in range(n)) > b + Fr(0) for a, b in all_rows
        ):
            continue
        value = sum(c[j] * x[j] for j in range(n))
        if best_value is None or value < best_value:
            best_value, best_x = value, x
    return best_value, best_x


# ---------------------------------------------------------------------------
# The two formulas.
# ---------------------------------------------------------------------------


def formula1_solution(
    qc: list[Fr], replacements: list[list[Fr]], eps: Fr
) -> tuple[Fr, list[Fr]]:
    n = len(qc)
    m = len(replacements)
    d = m + n
    c = [eps] * m + [Fr(1)] * n
    rows = []
    for v in range(n):
        row = [Fr(0)] * d
        for q in range(m):
            row[q] = -replacements[q][v]
        row[m + v] = Fr(-1)
        rows.append((tuple(row), -qc[v]))
    value, x = min_lp(c, rows, d)
    assert value is not None and x is not None
    return value, x[:m]


def formula1_value(qc: list[Fr], replacements: list[list[Fr]], eps: Fr) -> Fr:
    value, _ = formula1_solution(qc, replacements, eps)
    return value


def formula2_inner(qc: list[Fr], replacements: list[list[Fr]], s: Fr) -> Fr:
    """min over mu in the simplex of sum_v [qc(v) - s * sum_Q mu_Q Q(v)]_+."""

    n = len(qc)
    m = len(replacements)
    d = m + n
    c = [Fr(0)] * m + [Fr(1)] * n
    rows = [
        (tuple([Fr(1)] * m + [Fr(0)] * n), Fr(1)),
        (tuple([Fr(-1)] * m + [Fr(0)] * n), Fr(-1)),
    ]
    for v in range(n):
        row = [Fr(0)] * d
        for q in range(m):
            row[q] = -s * replacements[q][v]
        row[m + v] = Fr(-1)
        rows.append((tuple(row), -qc[v]))
    value, _ = min_lp(c, rows, d)
    assert value is not None
    return value




def in_convex_hull(qc: list[Fr], replacements: list[list[Fr]]) -> bool:
    n = len(qc)
    m = len(replacements)
    rows = []
    for v in range(n):
        row = tuple(replacements[q][v] for q in range(m))
        rows.append((row, qc[v]))
        rows.append((tuple(-x for x in row), -qc[v]))
    ones = tuple(Fr(1) for _ in range(m))
    rows.append((ones, Fr(1)))
    rows.append((tuple(-x for x in ones), Fr(-1)))
    value, _ = min_lp([Fr(0)] * m, rows, m)
    return value is not None


# ---------------------------------------------------------------------------
# Random instances and the formula-equivalence check.
# ---------------------------------------------------------------------------


def random_distribution(n: int, rng: random.Random, denom: int = 12) -> list[Fr]:
    while True:
        raw = [rng.randint(0, denom) for _ in range(n)]
        total = sum(raw)
        if total > 0:
            return [Fr(x, total) for x in raw]


def random_instance(
    n: int, m: int, rng: random.Random
) -> tuple[list[Fr], list[list[Fr]]]:
    return random_distribution(n, rng), [random_distribution(n, rng) for _ in range(m)]


def test_formula_equivalence(
    trials: int = 30,
    n: int = 3,
    m: int = 2,
    eps_values: tuple[Fr, ...] = (Fr(0), Fr(1, 20), Fr(1, 5), Fr(1, 2), Fr(1)),
) -> tuple[int, int]:
    """Check formula 1 against formula 2, evaluated exactly at s* = sum(lambda*).

    lambda* is formula 1's own optimal solution; formula 2's inner
    simplex-constrained problem is then re-solved at that exact s* by an
    independently coded linear program (not by reusing lambda*'s implied mu).
    Agreement is checked as an exact Fraction equality -- no grid, no
    floating-point tolerance.
    """

    rng = random.Random(20260714)
    checked = 0
    mismatches = 0
    for _ in range(trials):
        qc, replacements = random_instance(n, m, rng)
        for eps in eps_values:
            checked += 1
            exact, lambda_star = formula1_solution(qc, replacements, eps)
            s_star = sum(lambda_star)
            if s_star == 0:
                # formula 1 chose lambda=0: both formulas agree at the shared
                # s -> 0 boundary value of 1 by construction, nothing further
                # to re-solve.
                if exact != Fr(1):
                    mismatches += 1
                continue
            reconstructed = s_star * eps + formula2_inner(qc, replacements, s_star)
            if reconstructed != exact:
                mismatches += 1
    return checked, mismatches


# ---------------------------------------------------------------------------
# Separation corollary: hand-picked constructive cases.
# ---------------------------------------------------------------------------


def hand_picked_separation_cases():
    q1 = [Fr(1), Fr(0), Fr(0)]
    q2 = [Fr(0), Fr(1), Fr(0)]
    midpoint = [Fr(1, 2), Fr(1, 2), Fr(0)]
    yield "midpoint_is_in_hull", midpoint, [q1, q2], True, None

    q1b = [Fr(1, 2), Fr(1, 2), Fr(0)]
    q2b = [Fr(0), Fr(1), Fr(0)]
    outside = [Fr(3, 10), Fr(3, 10), Fr(4, 10)]
    phi = [Fr(0), Fr(0), Fr(1)]  # indicator of the outcome no replacement covers
    yield "uncovered_outcome_is_outside_hull", outside, [q1b, q2b], False, phi

    q1c = [Fr(1, 4), Fr(1, 4), Fr(1, 4), Fr(1, 4)]
    q2c = [Fr(1, 2), Fr(0), Fr(1, 2), Fr(0)]
    off_segment = [Fr(1, 3), Fr(1, 3), Fr(1, 3), Fr(0)]
    phi_c = [Fr(0), Fr(1), Fr(0), Fr(0)]
    yield (
        "off_segment_point_is_outside_hull",
        off_segment,
        [q1c, q2c],
        False,
        phi_c,
    )


def test_separation_corollary() -> list[tuple[str, bool]]:
    results = []
    for name, qc, replacements, expected_in_hull, phi in hand_picked_separation_cases():
        in_hull = in_convex_hull(qc, replacements)
        ok = in_hull == expected_in_hull
        if not expected_in_hull and ok:
            lhs = sum(phi[v] * qc[v] for v in range(len(qc)))
            rhs = max(
                sum(phi[v] * q[v] for v in range(len(qc))) for q in replacements
            )
            ok = lhs > rhs
        results.append((name, ok))
    return results


def main() -> None:
    start = time.perf_counter()
    total_checked = 0
    total_mismatches = 0
    for n, m, trials in ((3, 2, 30), (4, 3, 10)):
        checked, mismatches = test_formula_equivalence(trials=trials, n=n, m=m)
        total_checked += checked
        total_mismatches += mismatches
        print(f"shape_n{n}_m{m}_checked={checked}")
        print(f"shape_n{n}_m{m}_mismatches={mismatches}")
    elapsed = time.perf_counter() - start
    print(f"formula_equivalence_checked={total_checked}")
    print(f"formula_equivalence_mismatches={total_mismatches}")
    print(f"formula_equivalence_seconds={elapsed:.3f}")

    separation_results = test_separation_corollary()
    for name, ok in separation_results:
        print(f"separation_case_{name}={'PASS' if ok else 'FAIL'}")

    all_pass = total_mismatches == 0 and all(ok for _, ok in separation_results)
    print(f"replacement_hull_theorem={'PASS' if all_pass else 'FAIL'}")
    if not all_pass:
        raise SystemExit("replacement-hull verification failed")


if __name__ == "__main__":
    main()
