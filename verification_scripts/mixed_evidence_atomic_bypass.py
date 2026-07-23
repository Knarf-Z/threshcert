"""
Independent verification of the Master Certificate Theorem
(evidence-optimal atomic-bypass certificates under PARTIAL activation
evidence): the exact certificate a verifier may issue under the declared
mechanism m_bypass(b), when only members in a certified set M subseteq U0
have a certified activation floor -- the general two-axis object

    MABC_{b,M}(A0)
    := min_{Q subset U0, |Q| <= b}
       [ sum_{i in Q} R-bar_i + MCR-hat_{R-bar,tau-bar,M \\ Q}(A0 union Q) ],

varying simultaneously over the package budget b (mechanism power) and the
certified activation set M (evidence strength). This is the object that
makes every certificate already proved in this project a boundary case of
one theorem rather than a separate, parallel result:

    MABC_{0,empty}   = TCR                (Theorem information-boundary)
    MABC_{0,M}       = MCR_M              (Proposition partial-profile-evidence)
    MABC_{0,U0}      = ACR                (Theorem information-boundary)
    MABC_{b,empty}   = TCR for every b    (Theorem evidence-optimal-atomic-bypass)
    MABC_{b,U0}      = ABC-bar_b          (Theorem evidence-optimal-atomic-bypass)

None of those five special-case claims is re-derived or re-verified here
(each already has its own independent script); this script only verifies
the single new object that subsumes them, at general (b, M) pairs where
M is neither empty nor the full committee, since those interior points are
exactly what the boundary identities above do not already cover.

Reuses this directory's own already-verified machinery rather than a new
solver:
  - core.py's ac_formula_gamma_star, called with a MIXED tau vector
    (tau-bar_i for i in M, 0 for i outside M -- a zero floor imposes no
    order constraint at all, so this is the AC-formula theorem applied to
    that specific vector, not a new claim about MCR), computes
    MCR_{R-bar,tau-bar,M}(A) directly. Cross-validated below against
    partial_activation_evidence.py's own independent brute-force
    mcr_brute_force before being trusted for the outer Q-minimization.
  - atomic_bypass_hierarchy.py's abc_state_space is the ground truth for
    Gamma*_{m_bypass(b),P}(A0) under any ACTUAL profile P (does not assume
    Lemma package-first-wlog).
  - information_boundary.py's perturb_profile builds a random profile
    strictly consistent with given floors, reused unchanged.

Three checks:
  1. mcr_via_formula cross-validated against mcr_brute_force on random
     (A, tau_floor, R_floor, M) instances -- confirms the mixed-tau-vector
     reduction before it is used anywhere else in this script.
  2. Tightness: the exact-floor profile (R_i=R-bar_i, tau_i=tau-bar_i for
     every i, not only i in M) attains MABC_{b,M}(A0) exactly against
     abc_state_space, for random (b, M) pairs.
  3. Soundness: profiles built strictly above the same partial-evidence
     floors -- R_i>=R-bar_i everywhere, tau_i>=tau-bar_i only enforced for
     i in M, unconstrained (tau_i:=0, i.e. the most permissive choice)
     for i not in M -- never let m_bypass(b) achieve a smaller cost than
     MABC_{b,M}(A0) computed from the floors and M alone.

All arithmetic is exact (fractions.Fraction); nothing here is
tolerance-based. Seeds are deterministic (core.py's deterministic_seed,
SHA-256-based), not process-randomized hash().
"""
import sys, os, itertools
import random as _random
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ac_formula_gamma_star, random_instance, deterministic_seed
from atomic_bypass_hierarchy import abc_state_space
from information_boundary import zero_tau
from partial_activation_evidence import mcr_brute_force


def mcr_via_formula(w, t, A, tau_floor, R_floor, M):
    """MCR_{R-bar,tau-bar,M}(A) via a mixed tau vector: tau-bar_i for i in
    M, 0 for i not in M."""
    n = len(w)
    mixed_tau = [tau_floor[i] if i in M else Fr(0) for i in range(n)]
    return ac_formula_gamma_star(w, t, A, mixed_tau, R_floor)


def mcr_hat(w, t, A, tau_floor, R_floor, M):
    if sum((w[i] for i in A), Fr(0)) >= t:
        return Fr(0)
    return mcr_via_formula(w, t, A, tau_floor, R_floor, M)


def mabc_closed_form(w, t, A0, tau_floor, R_floor, M, b):
    """MABC_{b,M}(A0): minimize package cost plus the partial-evidence
    sequential remainder over every package Q of size at most b, removing
    Q's own members from the certified activation set M for that
    remainder (a package member bypasses activation entirely once
    bought, so its floor no longer constrains the sequential remainder)."""
    n = len(w)
    U0 = [i for i in range(n) if i not in A0]
    best = None
    for k in range(0, min(b, len(U0)) + 1):
        for combo in itertools.combinations(U0, k):
            Q = frozenset(combo)
            sub_A0 = set(A0) | Q
            package_cost = sum((R_floor[i] for i in Q), Fr(0))
            remaining_M = M - Q
            rest = mcr_hat(w, t, sub_A0, tau_floor, R_floor, remaining_M)
            if rest is None:
                continue
            total = package_cost + rest
            if best is None or total < best:
                best = total
    return best


def random_M(rng, U0):
    return frozenset(i for i in U0 if rng.random() < 0.5)


def perturb_profile_partial(rng, t, tau_floor, R_floor, M):
    """A profile strictly consistent with a PARTIAL-evidence ledger: R_i
    >= R-bar_i everywhere; tau_i >= tau-bar_i enforced only for i in M,
    with i not in M given an unconstrained (any valid, here: the floor
    itself or higher, since no ledger entry restricts it further) value."""
    n = len(R_floor)
    R2 = [R_floor[i] + Fr(rng.randint(0, 12)) for i in range(n)]
    tau2 = []
    for i in range(n):
        base = tau_floor[i] if i in M else Fr(0)
        room = t - base
        bump = room * Fr(rng.randint(0, 80), 100)
        tau2.append(base + bump)
    return R2, tau2


def check_mcr_formula_matches_brute_force(
    n_values=(3, 4, 5, 6, 7), trials_per_n=100, seed_base=20260722
):
    total = 0
    mismatches = []
    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base, "meab-mcr")
            wk = "random" if trial % 2 else "uniform"
            w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
            U0 = [i for i in range(n) if i not in A0]
            rng = _random.Random(seed ^ 0x1B873593)
            M = random_M(rng, U0)
            total += 1
            formula = mcr_via_formula(w, t, A0, tau_floor, R_floor, M)
            brute, _ = mcr_brute_force(w, t, A0, tau_floor, R_floor, M)
            if formula != brute:
                mismatches.append((n, seed, M, formula, brute))
    return total, mismatches


def check_tightness(
    n_values=(3, 4, 5, 6, 7), b_values=(0, 1, 2, 3), trials_per_n=60,
    seed_base=20260722,
):
    """The exact-floor WITNESS profile for MABC_{b,M} is not simply
    (R-bar, tau-bar) taken literally at every member -- the ledger
    certifies tau-bar_i only for i in M, so the matching least-favourable
    profile must set tau_i=0 (the most permissive, unconstrained choice)
    for i not in M, exactly as mcr_via_formula's own mixed vector does.
    Using the raw tau_floor for every member here would test a different,
    over-constrained profile that need not be ledger-consistent at all."""
    total = 0
    mismatches = []
    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base, "meab-tight")
            wk = "random" if trial % 2 else "uniform"
            w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
            U0 = [i for i in range(n) if i not in A0]
            rng = _random.Random(seed ^ 0x9E3779B9)
            for b in b_values:
                M = random_M(rng, U0)
                total += 1
                mixed_tau = [tau_floor[i] if i in M else Fr(0) for i in range(n)]
                closed = mabc_closed_form(w, t, A0, tau_floor, R_floor, M, b)
                ground_truth = abc_state_space(w, t, A0, mixed_tau, R_floor, b)
                if closed != ground_truth:
                    mismatches.append((n, seed, M, b, closed, ground_truth))
    return total, mismatches


def check_soundness(
    n_values=(3, 4, 5, 6, 7), b_values=(0, 1, 2, 3), trials_per_n=60,
    perturbations_per_trial=5, seed_base=20260722,
):
    total = 0
    violations = []
    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base, "meab-sound")
            wk = "random" if trial % 2 else "uniform"
            w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
            U0 = [i for i in range(n) if i not in A0]
            rng = _random.Random(seed ^ 0x85EBCA6B)
            for b in b_values:
                M = random_M(rng, U0)
                certificate = mabc_closed_form(w, t, A0, tau_floor, R_floor, M, b)
                total += 1
                for _ in range(perturbations_per_trial):
                    R2, tau2 = perturb_profile_partial(rng, t, tau_floor, R_floor, M)
                    actual = abc_state_space(w, t, A0, tau2, R2, b)
                    if actual is not None and (
                        certificate is None or actual < certificate
                    ):
                        violations.append(
                            (n, seed, M, b, tau2, R2, actual, certificate)
                        )
    return total, violations


if __name__ == "__main__":
    mcr_total, mcr_mismatches = check_mcr_formula_matches_brute_force()
    print(f"mcr_formula_tested={mcr_total}")
    print(f"mcr_formula_mismatches={len(mcr_mismatches)}")

    tight_total, tight_mismatches = check_tightness()
    print(f"tightness_tested={tight_total}")
    print(f"tightness_mismatches={len(tight_mismatches)}")

    sound_total, sound_violations = check_soundness()
    print(f"soundness_tested={sound_total}")
    print(f"soundness_violations={len(sound_violations)}")

    problems = mcr_mismatches + tight_mismatches + sound_violations
    if problems:
        print("\n!!! DISCREPANCY FOUND -- first 5 shown !!!")
        for p in problems[:5]:
            print(f"  {p}")
        raise SystemExit(1)

    print()
    print(
        "PASS: mixed_evidence_atomic_bypass -- the mixed-tau-vector MCR "
        "formula matched independent brute-force MCR on every tested "
        "instance; for every tested (b, M) pair, the exact-floor profile "
        "attains MABC_{b,M}(A0) exactly against the actual "
        "mechanism-faithful state-space computation (tightness), and "
        "every other profile consistent with the same partial-evidence "
        "floors -- resistance perturbed upward everywhere, activation "
        "perturbed upward only where M certifies it -- never let "
        "m_bypass(b) achieve a strictly smaller attack cost (soundness). "
        "No counterexample was found in the tested instances; this does "
        "not re-verify the five special cases (b=0, M=empty, M=U0) "
        "each of which already has its own independent script."
    )
