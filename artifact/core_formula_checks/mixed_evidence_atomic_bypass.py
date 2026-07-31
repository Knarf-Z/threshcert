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
  - information_boundary.py's cap-realizability rule is enforced for every
    generated witness and perturbed profile.

Three checks:
  1. mcr_via_formula cross-validated against mcr_brute_force on random
     (A, tau_floor, R_floor, M) instances -- confirms the mixed-tau-vector
     reduction before it is used anywhere else in this script.
  2. Tightness: when the mixed exact-floor witness is cap-realizable, it
     attains MABC_{b,M}(A0). If a certified positive gate is paired with
     zero resistance, executable epsilon-raised witnesses instead approach
     the same infimum.
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
from core import ac_formula_gamma_star, random_instance, deterministic_seed, parallel_map
from atomic_bypass_hierarchy import abc_state_space
from information_boundary import floor_profile_realizable, zero_tau
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


def epsilon_raise_profile(tau, resistance, eps):
    """Make the mixed scalar profile cap-realizable with at most eps extra
    resistance per member."""
    return [
        r + eps if r == 0 and gate > 0 else r
        for gate, r in zip(tau, resistance)
    ]


def perturb_profile_partial(rng, t, tau_floor, R_floor, M):
    """A cap-realizable profile consistent with a partial-evidence ledger:
    resistance floors hold everywhere and activation floors only on M."""
    n = len(R_floor)
    R2 = [R_floor[i] + Fr(rng.randint(0, 12)) for i in range(n)]
    tau2 = []
    for i in range(n):
        base = tau_floor[i] if i in M else Fr(0)
        room = t - base
        bump = room * Fr(rng.randint(0, 80), 100)
        tau2.append(base + bump)
    for i in range(n):
        if R2[i] == 0 and tau2[i] > 0:
            R2[i] = Fr(1)
    return R2, tau2


def _check_mcr_formula_matches_brute_force_one(task):
    n, trial, seed_base = task
    seed = deterministic_seed(n, trial, seed_base, "meab-mcr")
    wk = "random" if trial % 2 else "uniform"
    w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
    U0 = [i for i in range(n) if i not in A0]
    rng = _random.Random(seed ^ 0x1B873593)
    M = random_M(rng, U0)
    formula = mcr_via_formula(w, t, A0, tau_floor, R_floor, M)
    brute, _ = mcr_brute_force(w, t, A0, tau_floor, R_floor, M)
    if formula != brute:
        return (n, seed, M, formula, brute)
    return None


def check_mcr_formula_matches_brute_force(
    n_values=(3, 4, 5, 6, 7), trials_per_n=100, seed_base=20260722
):
    tasks = [(n, trial, seed_base) for n in n_values for trial in range(trials_per_n)]
    results = parallel_map(_check_mcr_formula_matches_brute_force_one, tasks)
    total = len(tasks)
    mismatches = [m for m in results if m is not None]
    return total, mismatches


def _check_tightness_one(task):
    n, trial, b_values, seed_base = task
    seed = deterministic_seed(n, trial, seed_base, "meab-tight")
    wk = "random" if trial % 2 else "uniform"
    w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
    U0 = [i for i in range(n) if i not in A0]
    rng = _random.Random(seed ^ 0x9E3779B9)
    mismatches = []
    for b in b_values:
        M = random_M(rng, U0)
        mixed_tau = [tau_floor[i] if i in M else Fr(0) for i in range(n)]
        certificate = mabc_closed_form(w, t, A0, tau_floor, R_floor, M, b)
        if floor_profile_realizable(mixed_tau, R_floor):
            actual = abc_state_space(w, t, A0, mixed_tau, R_floor, b)
            if certificate != actual:
                mismatches.append(
                    (n, seed, M, b, "attained", certificate, actual)
                )
        else:
            eps = Fr(1, 1000)
            R_eps = epsilon_raise_profile(mixed_tau, R_floor, eps)
            actual = abc_state_space(w, t, A0, mixed_tau, R_eps, b)
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
                    (n, seed, M, b, "approached", certificate, actual, eps)
                )
    return len(b_values), mismatches


def check_tightness(
    n_values=(3, 4, 5, 6, 7), b_values=(0, 1, 2, 3), trials_per_n=60,
    seed_base=20260722,
):
    """Use the mixed gate vector certified on M and zero elsewhere. Test
    exact attainment when it is cap-realizable; otherwise test an executable
    epsilon approach bounded by n*epsilon."""
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
    n, trial, b_values, perturbations_per_trial, seed_base = task
    seed = deterministic_seed(n, trial, seed_base, "meab-sound")
    wk = "random" if trial % 2 else "uniform"
    w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
    U0 = [i for i in range(n) if i not in A0]
    rng = _random.Random(seed ^ 0x85EBCA6B)
    violations = []
    for b in b_values:
        M = random_M(rng, U0)
        certificate = mabc_closed_form(w, t, A0, tau_floor, R_floor, M, b)
        for _ in range(perturbations_per_trial):
            R2, tau2 = perturb_profile_partial(rng, t, tau_floor, R_floor, M)
            actual = abc_state_space(w, t, A0, tau2, R2, b)
            if actual is not None and (
                certificate is None or actual < certificate
            ):
                violations.append((n, seed, M, b, tau2, R2, actual, certificate))
    return len(b_values), violations


def check_soundness(
    n_values=(3, 4, 5, 6, 7), b_values=(0, 1, 2, 3), trials_per_n=60,
    perturbations_per_trial=5, seed_base=20260722,
):
    tasks = [
        (n, trial, b_values, perturbations_per_trial, seed_base)
        for n in n_values
        for trial in range(trials_per_n)
    ]
    results = parallel_map(_check_soundness_one, tasks)
    total = sum(r[0] for r in results)
    violations = [v for _, vs in results for v in vs]
    return total, violations



def check_strict_infimum_fixture():
    """Partial-evidence strict infimum at M={1}, for all feasible package
    budgets in the two-member instance."""
    w = [Fr(1, 2), Fr(1, 2)]
    t = Fr(1)
    A0 = set()
    tau_floor = [Fr(0), Fr(1, 2)]
    R_floor = [Fr(1), Fr(0)]
    M = frozenset({1})
    mixed_tau = [Fr(0), Fr(1, 2)]
    mismatches = []
    epsilons = [Fr(1, 10), Fr(1, 100), Fr(1, 1000), Fr(1, 10000)]
    for b in (0, 1, 2):
        certificate = mabc_closed_form(w, t, A0, tau_floor, R_floor, M, b)
        if certificate != Fr(1):
            mismatches.append(("certificate", b, certificate))
            continue
        for eps in epsilons:
            R_eps = epsilon_raise_profile(mixed_tau, R_floor, eps)
            actual = abc_state_space(w, t, A0, mixed_tau, R_eps, b)
            if actual != certificate + eps:
                mismatches.append(
                    ("epsilon", b, eps, actual, certificate + eps)
                )
    return 3 * len(epsilons), mismatches
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

    strict_total, strict_mismatches = check_strict_infimum_fixture()
    print(f"strict_infimum_epsilon_profiles_tested={strict_total}")
    print(f"strict_infimum_mismatches={len(strict_mismatches)}")

    problems = (
        mcr_mismatches
        + tight_mismatches
        + sound_violations
        + strict_mismatches
    )
    if problems:
        print("\n!!! DISCREPANCY FOUND -- first 5 shown !!!")
        for p in problems[:5]:
            print(f"  {p}")
        raise SystemExit(1)

    print()
    print(
        "PASS: mixed_evidence_atomic_bypass -- the mixed-tau-vector MCR "
        "formula matched independent brute-force MCR on every tested "
        "instance. Cap-realizable mixed exact-floor witnesses attained "
        "MABC_{b,M}(A0), while epsilon-raised witnesses approached every "
        "non-realizable tested floor vector against the mechanism-faithful "
        "state space. Other cap-realizable profiles consistent with the "
        "same partial-evidence floors never achieved a smaller cost. A "
        "dedicated fixture confirmed a strict MABC infimum for every "
        "feasible package budget."
    )