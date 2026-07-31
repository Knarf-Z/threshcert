"""
Independent verification of the evidence-optimal extension of the
atomic-bypass mechanism hierarchy (Theorem evidence-optimal-atomic-bypass):
given only a certified evidence LEDGER of floors (R-bar, tau-bar) -- not a
known exact profile -- under the DECLARED mechanism m_bypass(b), the
largest universally sound attack-cost certificate is exactly

    0                                    at public evidence only,
    TCR_{R-bar}(A0)                      at resistance floors only,
    ABC-bar_b(A0)                        at resistance + activation floors,

where ABC-bar_b(A0) := min over Q subset U0, |Q|<=b of
[ sum_{i in Q} R-bar_i + ACR-hat_{R-bar,tau-bar}(A0 union Q) ], mirroring
exactly how Theorem atomic-bypass-hierarchy itself is built from the
sequential mechanism's own Gamma*_seq, but now with floors standing in for
an exact profile and ACR standing in for Gamma*_seq.

This closes the gap the one-shot atomic-bypass hierarchy (this directory's
atomic_bypass_hierarchy.py) deliberately left open: that theorem is an
*exact-profile* operational characterization (Gamma*_{m_bypass(b),P}(A0)
for a KNOWN profile P), not yet a certificate a verifier can issue from
floors alone the way Theorem information-boundary already is for the
sequential mechanism. ABC-bar_b is exactly that certificate for
m_bypass(b), interpolating between ACR (b=0) and TCR (b>=b*) the same way
ABC_b interpolates between Gamma*_seq and TCR for a known profile.

Reuses this directory's own already-verified machinery rather than a new
solver:
  - core.py's ac_formula_gamma_star computes ACR_{R,tau}(A) directly when
    called with floors standing in for an exact profile (R=R-bar,
    tau=tau-bar); this is not a new claim, just the AC-formula theorem
    applied to a specific profile equal to the floors.
  - atomic_bypass_hierarchy.py's abc_closed_form(w,t,A0,tau,R,b), called
    with floors standing in for an exact profile, therefore computes
    ABC-bar_b(A0) directly -- again just Theorem atomic-bypass-hierarchy
    applied to that specific profile, not a new formula.
  - atomic_bypass_hierarchy.py's abc_state_space is the ground truth for
    Gamma*_{m_bypass(b),P}(A0) under any ACTUAL profile P, used below to
    check every profile consistent with the floors, not just the floors
    themselves.
  - information_boundary.py's cap-realizability predicate and
    perturb_profile helper keep every tested scalar threshold inside the
    canonical cap class.

Two independent directions, exactly mirroring information_boundary.py's
own tightness/soundness split:

  1. Tightness: when the exact-floor vector is cap-realizable,
     abc_state_space computed directly on it matches the certificate.
     If R-bar_i=0<tau-bar_i for some member, no nonnegative cap realizes
     that exact vector; executable epsilon-raised profiles instead
     approach the same certificate from above.

  2. Soundness: no OTHER profile consistent with the same floors ever
     lets m_bypass(b) beat the floors-based certificate. For each random
     ledger, several random profiles are built strictly above the floors
     (resistance and/or activation, including the all-zero-tau
     most-permissive case) and abc_state_space's actual mechanism-faithful
     Gamma*_{m_bypass(b)} is checked against ABC-bar_b for every such
     profile and every b.

A further pair of checks reproduces the two degenerate boundary layers
computationally: public-only evidence (R-bar=0, tau-bar=0) collapses
ABC-bar_b to exactly zero for every b, and resistance-only evidence
(tau-bar=0, i.e. no certified activation floor at all) collapses
ABC-bar_b to exactly TCR_{R-bar}(A0) for every b -- a package buys nothing
when there is no activation gate to bypass in the first place, matching
claim (ii) in the theorem statement.

All arithmetic is exact (fractions.Fraction); nothing here is
tolerance-based. Seeds are deterministic (core.py's deterministic_seed,
SHA-256-based), not process-randomized hash().
"""
import sys, os
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ac_formula_gamma_star, random_instance, deterministic_seed, parallel_map
from atomic_bypass_hierarchy import abc_closed_form, abc_state_space
from information_boundary import (
    floor_profile_realizable,
    perturb_profile,
    zero_tau,
)


def epsilon_raise_profile(tau_floor, R_floor, eps):
    """Make a floor vector cap-realizable with at most eps extra resistance
    per member. Only zero-resistance, positive-threshold coordinates need
    to move."""
    return [
        r + eps if r == 0 and gate > 0 else r
        for gate, r in zip(tau_floor, R_floor)
    ]


def _check_tightness_one(task):
    n, trial, b_values, seed_base = task
    seed = deterministic_seed(n, trial, seed_base, "eoab-tight")
    wk = "random" if trial % 2 else "uniform"
    w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
    mismatches = []
    for b in b_values:
        certificate = abc_closed_form(w, t, A0, tau_floor, R_floor, b)
        if floor_profile_realizable(tau_floor, R_floor):
            actual = abc_state_space(w, t, A0, tau_floor, R_floor, b)
            if certificate != actual:
                mismatches.append(
                    (n, seed, b, "attained", certificate, actual)
                )
        else:
            eps = Fr(1, 1000)
            R_eps = epsilon_raise_profile(tau_floor, R_floor, eps)
            actual = abc_state_space(w, t, A0, tau_floor, R_eps, b)
            if (
                (certificate is None and actual is not None)
                or (
                    certificate is not None
                    and (
                        actual is None
                        or actual < certificate
                        or actual > certificate + n * eps
                    )
                )
            ):
                mismatches.append(
                    (n, seed, b, "approached", certificate, actual, eps)
                )
    return len(b_values), mismatches


def check_tightness(
    n_values=(3, 4, 5, 6, 7), b_values=(0, 1, 2, 3), trials_per_n=40,
    seed_base=20260722,
):
    """Cap-realizable exact-floor profiles attain ABC-bar_b(A0); otherwise
    executable epsilon-raised profiles approach it within n*epsilon. Both
    checks use the actual mechanism-faithful state-space computation."""
    tasks = [
        (n, trial, b_values, seed_base)
        for n in n_values
        for trial in range(trials_per_n)
    ]
    results = parallel_map(_check_tightness_one, tasks)
    total = sum(r[0] for r in results)
    mismatches = [m for _, ms in results for m in ms]
    return total, mismatches


def _check_soundness_one(task):
    import random as _random

    n, trial, b_values, perturbations_per_trial, seed_base = task
    seed = deterministic_seed(n, trial, seed_base, "eoab-sound")
    wk = "random" if trial % 2 else "uniform"
    w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
    rng = _random.Random(seed ^ 0x2545F491)
    violations = []
    for b in b_values:
        certificate = abc_closed_form(w, t, A0, tau_floor, R_floor, b)
        for _ in range(perturbations_per_trial):
            R2, tau2 = perturb_profile(rng, t, tau_floor, R_floor)
            actual = abc_state_space(w, t, A0, tau2, R2, b)
            if actual is not None and (
                certificate is None or actual < certificate
            ):
                violations.append(
                    (n, seed, b, "perturbed", tau2, R2, actual, certificate)
                )
            # Most-permissive tau (all zero): the resistance-only
            # layer's collapse-to-TCR claim needs no positive
            # activation floor certified at all.
            actual_zero_tau = abc_state_space(w, t, A0, zero_tau(n), R2, b)
            tcr_certificate = ac_formula_gamma_star(w, t, A0, zero_tau(n), R_floor)
            if actual_zero_tau is not None and (
                tcr_certificate is None or actual_zero_tau < tcr_certificate
            ):
                violations.append(
                    (n, seed, b, "zero-tau", R2, actual_zero_tau, tcr_certificate)
                )
    return len(b_values), violations


def check_soundness(
    n_values=(3, 4, 5, 6, 7), b_values=(0, 1, 2, 3), trials_per_n=40,
    perturbations_per_trial=5, seed_base=20260722,
):
    """No profile consistent with the floors ever lets m_bypass(b) beat
    the floors-based certificate ABC-bar_b(A0)."""
    tasks = [
        (n, trial, b_values, perturbations_per_trial, seed_base)
        for n in n_values
        for trial in range(trials_per_n)
    ]
    results = parallel_map(_check_soundness_one, tasks)
    total = sum(r[0] for r in results)
    violations = [v for _, vs in results for v in vs]
    return total, violations


def _check_public_only_one(task):
    n, trial, b_values, seed_base = task
    seed = deterministic_seed(n, trial, seed_base, "eoab-pub")
    w, t, A0, _, _ = random_instance(n, seed)
    zero_R = [Fr(0)] * n
    mismatches = []
    for b in b_values:
        value = abc_closed_form(w, t, A0, zero_tau(n), zero_R, b)
        if value != Fr(0):
            mismatches.append((n, seed, b, value))
    return len(b_values), mismatches


def check_public_only(n_values=(3, 5, 7), b_values=(0, 1, 2, 3), trials_per_n=20,
                       seed_base=20260722):
    """I_pub: no resistance floor and no activation floor certified at
    all -- ABC-bar_b(A0) must collapse to exactly zero for every b."""
    tasks = [
        (n, trial, b_values, seed_base)
        for n in n_values
        for trial in range(trials_per_n)
    ]
    results = parallel_map(_check_public_only_one, tasks)
    total = sum(r[0] for r in results)
    mismatches = [m for _, ms in results for m in ms]
    return total, mismatches


def _check_resistance_only_collapses_to_tcr_one(task):
    n, trial, b_values, seed_base = task
    seed = deterministic_seed(n, trial, seed_base, "eoab-res")
    wk = "random" if trial % 2 else "uniform"
    w, t, A0, _, R_floor = random_instance(n, seed, weight_kind=wk)
    tcr = ac_formula_gamma_star(w, t, A0, zero_tau(n), R_floor)
    mismatches = []
    for b in b_values:
        value = abc_closed_form(w, t, A0, zero_tau(n), R_floor, b)
        if value != tcr:
            mismatches.append((n, seed, b, value, tcr))
    return len(b_values), mismatches


def check_resistance_only_collapses_to_tcr(
    n_values=(3, 4, 5, 6, 7), b_values=(0, 1, 2, 3), trials_per_n=30,
    seed_base=20260722,
):
    """I_R: resistance floors certified, no activation floor at all
    (tau-bar=0) -- ABC-bar_b(A0) must equal TCR_{R-bar}(A0) exactly for
    every b, regardless of the package budget."""
    tasks = [
        (n, trial, b_values, seed_base)
        for n in n_values
        for trial in range(trials_per_n)
    ]
    results = parallel_map(_check_resistance_only_collapses_to_tcr_one, tasks)
    total = sum(r[0] for r in results)
    mismatches = [m for _, ms in results for m in ms]
    return total, mismatches



def check_strict_infimum_fixture():
    """A two-member floor ledger for which every package budget has value
    one, but no exact-floor canonical profile exists."""
    w = [Fr(1, 2), Fr(1, 2)]
    t = Fr(1)
    A0 = set()
    tau_floor = [Fr(0), Fr(1, 2)]
    R_floor = [Fr(1), Fr(0)]
    mismatches = []
    epsilons = [Fr(1, 10), Fr(1, 100), Fr(1, 1000), Fr(1, 10000)]
    for b in (0, 1, 2):
        certificate = abc_closed_form(w, t, A0, tau_floor, R_floor, b)
        if certificate != Fr(1):
            mismatches.append(("certificate", b, certificate))
            continue
        for eps in epsilons:
            R_eps = epsilon_raise_profile(tau_floor, R_floor, eps)
            actual = abc_state_space(w, t, A0, tau_floor, R_eps, b)
            if actual != certificate + eps:
                mismatches.append(
                    ("epsilon", b, eps, actual, certificate + eps)
                )
    return 3 * len(epsilons), mismatches
if __name__ == "__main__":
    tight_total, tight_mismatches = check_tightness()
    print(f"tightness_tested={tight_total}")
    print(f"tightness_mismatches={len(tight_mismatches)}")

    sound_total, sound_violations = check_soundness()
    print(f"soundness_tested={sound_total}")
    print(f"soundness_violations={len(sound_violations)}")

    pub_total, pub_mismatches = check_public_only()
    print(f"public_only_tested={pub_total}")
    print(f"public_only_mismatches={len(pub_mismatches)}")

    res_total, res_mismatches = check_resistance_only_collapses_to_tcr()
    print(f"resistance_only_tested={res_total}")
    print(f"resistance_only_mismatches={len(res_mismatches)}")

    strict_total, strict_mismatches = check_strict_infimum_fixture()
    print(f"strict_infimum_epsilon_profiles_tested={strict_total}")
    print(f"strict_infimum_mismatches={len(strict_mismatches)}")

    problems = (
        tight_mismatches
        + sound_violations
        + pub_mismatches
        + res_mismatches
        + strict_mismatches
    )
    if problems:
        print("\n!!! DISCREPANCY FOUND -- first 5 shown !!!")
        for p in problems[:5]:
            print(f"  {p}")
        raise SystemExit(1)

    print()
    print(
        "PASS: evidence_optimal_atomic_bypass -- for every tested evidence "
        "ledger and package budget b, every cap-realizable exact-floor "
        "profile attained ABC-bar_b(A0), while epsilon-raised profiles "
        "approached non-realizable floor vectors against the actual "
        "mechanism-faithful state-space computation. Every other profile "
        "consistent with the same floors -- resistance and/or activation "
        "perturbed upward, including the most-permissive all-zero-tau case "
        "-- never let m_bypass(b) achieve a strictly smaller attack cost "
        "(soundness). Public-only evidence collapsed the certificate to "
        "exactly zero, and resistance-only evidence collapsed it to exactly "
        "TCR_{R-bar}(A0) regardless of b. A dedicated fixture confirmed a "
        "strict ABC-bar_b infimum for every feasible package budget."
    )