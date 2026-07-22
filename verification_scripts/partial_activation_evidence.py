"""
Independent stress-test of Proposition (Certificate under partial
activation-floor evidence): the MCR_{R-bar,tau-bar,M} certificate that
interpolates between TCR (M = empty) and ACR (M = full committee) as the
evidence ledger certifies an activation floor for only some members
M subseteq U0. This proposition, and the accompanying remediation
monotonicity result, are new in this pass -- the main text's own
"Verification" paragraph for this section points to a script in the
supplementary artifact; this is that script.

Reuses core.py's brute_force_gamma_star (ground truth) and
ac_formula_gamma_star (already-verified TCR/ACR special cases) rather than
reimplementing them; only the new M-partial combinatorics are written
here.

Checks, on random small instances:
  1. Boundary consistency: MCR at M = empty matches TCR and at M = full U0
     matches ACR, both computed via core.py's own ac_formula_gamma_star.
  2. Monotonicity (Proposition remediation-monotone): growing M along a
     random chain never decreases MCR, in the extended-reals sense where
     "no feasible cover" (None) is the top element.
  3. Tightness: the exact least-favourable profile from the proposition's
     own proof (non-M members front-loaded/always active, M-members given
     a step cap at their certified floor, with the same epsilon
     perturbation used there for the degenerate zero-floor case) attains
     MCR_M + |S*|*epsilon exactly -- checked by brute-force sequential
     search on that literal constructed profile, not a floating-point
     approximation.
  4. Soundness: profiles consistent with 𝔓_M(A0) -- M-member floors and
     activation independently perturbed upward, non-M members given an
     UNCONSTRAINED (random) activation floor, since the evidence certifies
     nothing about them -- never produce a smaller brute-force attack cost
     than MCR_M.

All arithmetic is exact (fractions.Fraction); nothing here is
tolerance-based.
"""
import sys, os, random
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (
    brute_force_gamma_star,
    ac_formula_gamma_star,
    random_instance,
    deterministic_seed,
)

_ZERO_TAU_CACHE = {}
_BIG_R = Fr(10**9)


def zero_tau(n):
    if n not in _ZERO_TAU_CACHE:
        _ZERO_TAU_CACHE[n] = [Fr(0)] * n
    return _ZERO_TAU_CACHE[n]


def mcr_brute_force(w, t, A0, tau_floor, R_floor, M):
    """Brute-force MCR_{R-bar,tau-bar,M}(A0) and a minimal witness set.

    S is in F+_M(A0) iff some order of S lets every i in S & M meet its
    floor (tau_i <= cumulative exposure before it) while members in S - M
    face no ordering constraint at all. Since non-M members impose no
    constraint and only add exposure, the optimal witnessing order always
    front-loads them; checking feasibility therefore reduces to: place all
    of S - M first, then process S & M in nondecreasing tau order -- the
    same canonical-order argument as the M = U0 case in core.py, just
    restricted to M.

    Returns (best_cost_or_None, witness_set_or_None).
    """
    n = len(w)
    U0 = [i for i in range(n) if i not in A0]
    a0_exposure = sum(w[i] for i in A0)
    best = None
    best_S = None
    m = len(U0)
    for mask in range(1, 1 << m):
        S = [U0[j] for j in range(m) if (mask >> j) & 1]
        if a0_exposure + sum(w[i] for i in S) < t:
            continue
        non_m = [i for i in S if i not in M]
        m_members = sorted((i for i in S if i in M), key=lambda i: tau_floor[i])
        exposure = a0_exposure + sum(w[i] for i in non_m)
        feasible = True
        for i in m_members:
            if tau_floor[i] > exposure:
                feasible = False
                break
            exposure += w[i]
        if not feasible:
            continue
        cost = sum(R_floor[i] for i in S)
        if best is None or cost < best:
            best, best_S = cost, S
    return best, best_S


def leq_extended(a, b):
    """a <= b where None represents +infinity."""
    if a is None:
        return b is None
    if b is None:
        return True
    return a <= b


def check_boundary_and_monotonicity(
    n_values=(3, 4, 5, 6, 7), trials_per_n=40, seed_base=20260722
):
    total = 0
    boundary_mismatches = []
    monotonicity_violations = []

    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base)
            wk = "random" if trial % 2 else "uniform"
            w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
            U0 = [i for i in range(n) if i not in A0]
            total += 1

            tcr = ac_formula_gamma_star(w, t, A0, zero_tau(n), R_floor)
            acr = ac_formula_gamma_star(w, t, A0, tau_floor, R_floor)
            mcr_empty, _ = mcr_brute_force(w, t, A0, tau_floor, R_floor, frozenset())
            mcr_full, _ = mcr_brute_force(
                w, t, A0, tau_floor, R_floor, frozenset(U0)
            )
            if mcr_empty != tcr or mcr_full != acr:
                boundary_mismatches.append((n, seed, mcr_empty, tcr, mcr_full, acr))

            rng = random.Random(seed ^ 0x1234)
            order = U0[:]
            rng.shuffle(order)
            prev_mcr, prev_M = mcr_empty, frozenset()
            for i in order:
                M = prev_M | {i}
                mcr_M, _ = mcr_brute_force(w, t, A0, tau_floor, R_floor, M)
                if not leq_extended(prev_mcr, mcr_M):
                    monotonicity_violations.append(
                        (n, seed, prev_M, M, prev_mcr, mcr_M)
                    )
                prev_mcr, prev_M = mcr_M, M

    return total, boundary_mismatches, monotonicity_violations


def check_tightness_and_soundness(
    n_values=(3, 4, 5, 6, 7),
    trials_per_n=40,
    perturbations_per_trial=5,
    seed_base=20260722,
):
    total = 0
    tightness_mismatches = []
    soundness_violations = []

    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base, "tight")
            wk = "random" if trial % 2 else "uniform"
            w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
            U0 = [i for i in range(n) if i not in A0]
            rng = random.Random(seed ^ 0x5BD1E995)
            M = frozenset(i for i in U0 if rng.random() < 0.5)
            total += 1

            B_M, S_star = mcr_brute_force(w, t, A0, tau_floor, R_floor, M)
            if B_M is None:
                continue  # nothing to construct; soundness alone gives +inf

            # --- Tightness: the exact least-favourable profile.
            delta = Fr(1, 1000)
            R_eps = [
                (R_floor[i] + delta) if i in S_star else _BIG_R
                for i in range(n)
            ]
            tau_eps = [
                (tau_floor[i] if i in M else Fr(0)) if i in S_star else Fr(0)
                for i in range(n)
            ]
            brute = brute_force_gamma_star(w, t, A0, tau_eps, R_eps)
            expected = B_M + len(S_star) * delta
            if brute != expected:
                tightness_mismatches.append((n, seed, M, S_star, brute, expected))

            # --- Soundness: nothing consistent with the M-partial ledger
            # beats B_M. M-members perturbed upward within [floor, t);
            # non-M members given a random, UNCONSTRAINED activation
            # floor, since the ledger certifies nothing about them.
            for _ in range(perturbations_per_trial):
                R2 = [R_floor[i] + Fr(rng.randint(0, 12)) for i in range(n)]
                tau2 = []
                for i in range(n):
                    if i in M:
                        room = t - tau_floor[i]
                        bump = room * Fr(rng.randint(0, 80), 100)
                        tau2.append(tau_floor[i] + bump)
                    else:
                        tau2.append(t * Fr(rng.randint(0, 99), 100))
                bf_pert = brute_force_gamma_star(w, t, A0, tau2, R2)
                if bf_pert is not None and bf_pert < B_M:
                    soundness_violations.append((n, seed, M, tau2, R2, bf_pert, B_M))

    return total, tightness_mismatches, soundness_violations


if __name__ == "__main__":
    b_total, boundary_mismatches, monotonicity_violations = (
        check_boundary_and_monotonicity()
    )
    t_total, tightness_mismatches, soundness_violations = (
        check_tightness_and_soundness()
    )

    print(f"boundary_instances_tested={b_total}")
    print(f"boundary_mismatches={len(boundary_mismatches)}")
    print(f"monotonicity_chains_tested={b_total}")
    print(f"monotonicity_violations={len(monotonicity_violations)}")
    print(f"tightness_soundness_instances_tested={t_total}")
    print(f"tightness_mismatches={len(tightness_mismatches)}")
    print(f"soundness_violations={len(soundness_violations)}")

    all_problems = (
        boundary_mismatches
        + monotonicity_violations
        + tightness_mismatches
        + soundness_violations
    )
    if all_problems:
        print("\n!!! DISCREPANCY FOUND -- first 5 shown !!!")
        for p in all_problems[:5]:
            print(f"  {p}")
        raise SystemExit(1)

    print(
        "PASS: partial_activation_evidence -- MCR at M=empty/full matches "
        "TCR/ACR exactly on every tested instance; MCR never decreased "
        "along a random chain of growing M (monotonicity); the exact "
        "least-favourable profile from the proposition's own proof "
        "attained MCR_M + |S*|*epsilon exactly on every instance where "
        "MCR_M was finite (tightness); and profiles consistent with the "
        "same partial evidence -- M-members perturbed upward, non-M "
        "members given an unconstrained random activation floor -- never "
        "certified a smaller attack cost (soundness)."
    )
