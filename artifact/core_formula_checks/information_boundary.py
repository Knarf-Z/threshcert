"""
Independent stress-test of Theorem (information-boundary): "Evidence-optimal
certificates under activation scope" -- the paper's central result, added in
a later pass once main_text.tex became available on this machine.

test_equivalence.py already checks the (AC) reduction for a single FIXED
profile: Gamma*(A0) == min_{S in T+(A0)} sum R_i for that profile's own
(tau, R). The information-boundary theorem is a different, higher-level
claim: given only a certified evidence LEDGER of floors (R-bar, tau-bar), it
characterizes the infimum of Gamma*_P(A0) over EVERY profile P consistent
with that ledger (R_i >= R-bar_i, tau_i >= tau-bar_i, weakly increasing
right-continuous caps) as exactly TCR_{R-bar}(A0) (resistance floors only)
or ACR_{R-bar,tau-bar}(A0) (resistance and activation floors), with no larger
value soundly certifiable from the same evidence.

TCR and ACR both reduce to one call each to core.py's already-verified
ac_formula_gamma_star (TCR uses an all-zero tau vector, since a floor of
zero imposes no activation-order constraint at all; ACR uses the floors
directly). This script does not re-derive that reduction -- it tests the
CLAIM ABOUT THE LEDGER'S INFIMUM instead, via two independent directions on
many random small instances:

  1. Tightness: when the exact-floor scalar thresholds are cap-realizable,
     that profile attains the certificate. If R-bar_i=0<tau-bar_i, nonnegative
     caps make exact attainment impossible; executable epsilon-profiles must
     instead approach the same infimum.
  2. Soundness: no OTHER profile consistent with the same floors ever beats
     the certificate. For each random ledger, several random profiles are
     built strictly above the floors (in resistance, in activation, or
     both -- including the all-zero-tau, most-permissive case used for the
     mechanism-robust TCR claim) and brute-force Gamma* is checked against
     the certificate computed from the floors alone.

Separate checks reproduce the public-only branch, where the all-zero profile
attains zero, and a strict-infimum fixture with R-bar_i=0<tau-bar_i, where no
exact-floor cap profile exists but executable epsilon-profiles converge to ACR.

All arithmetic is exact (fractions.Fraction); nothing here is tolerance-based.
"""
import sys, os, random
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (
    brute_force_gamma_star,
    ac_formula_gamma_star,
    random_instance,
    deterministic_seed,
    parallel_map,
)

_ZERO_TAU_CACHE = {}


def zero_tau(n):
    if n not in _ZERO_TAU_CACHE:
        _ZERO_TAU_CACHE[n] = [Fr(0)] * n
    return _ZERO_TAU_CACHE[n]

def floor_profile_realizable(tau, resistance):
    """A scalar threshold is realizable by a nonnegative monotone cap iff
    zero resistance is not paired with a positive threshold."""
    return all(not (r == 0 and gate > 0) for gate, r in zip(tau, resistance))


def perturb_profile(rng, t, tau_floor, R_floor):
    """One profile strictly consistent with the floors: R_i' >= R-bar_i, and
    tau_i' >= tau-bar_i while remaining in the valid [tau-bar_i, t) exposure
    domain. The zero-resistance/positive-threshold pair is excluded because
    no nonnegative weakly increasing cap can realize it."""
    n = len(R_floor)
    R2 = [R_floor[i] + Fr(rng.randint(0, 12)) for i in range(n)]
    tau2 = []
    for i in range(n):
        room = t - tau_floor[i]
        bump = room * Fr(rng.randint(0, 80), 100)
        tau2.append(tau_floor[i] + bump)
    for i in range(n):
        if R2[i] == 0 and tau2[i] > 0:
            R2[i] = Fr(1)
    return R2, tau2


def _check_tightness_and_soundness_one(task):
    n, trial, perturbations_per_trial, seed_base = task
    seed = deterministic_seed(n, trial, seed_base)
    wk = "random" if trial % 2 else "uniform"
    w, t, A0, tau_floor, R_floor = random_instance(n, seed, weight_kind=wk)
    rng = random.Random(seed ^ 0x5BD1E995)

    tightness_mismatches = []
    soundness_violations = []

    acr = ac_formula_gamma_star(w, t, A0, tau_floor, R_floor)
    tcr = ac_formula_gamma_star(w, t, A0, zero_tau(n), R_floor)

    # --- Tightness: TCR is attained. ACR is attained exactly when the floor
    # profile is cap-realizable; otherwise executable epsilon profiles approach it.
    brute_tcr = brute_force_gamma_star(w, t, A0, zero_tau(n), R_floor)
    if brute_tcr != tcr:
        tightness_mismatches.append((n, seed, "tcr", brute_tcr, tcr))
    if floor_profile_realizable(tau_floor, R_floor):
        brute_acr = brute_force_gamma_star(w, t, A0, tau_floor, R_floor)
        if brute_acr != acr:
            tightness_mismatches.append((n, seed, "acr-attained", brute_acr, acr))
    else:
        eps = Fr(1, 1000)
        R_eps = [r + eps if r == 0 and gate > 0 else r
                 for gate, r in zip(tau_floor, R_floor)]
        brute_eps = brute_force_gamma_star(w, t, A0, tau_floor, R_eps)
        if ((acr is None and brute_eps is not None) or
            (acr is not None and
             (brute_eps is None or brute_eps < acr or brute_eps > acr + n * eps))):
            tightness_mismatches.append(
                (n, seed, "acr-approached", brute_eps, acr, eps)
            )

    # --- Soundness: nothing consistent with the floors beats them.
    for _ in range(perturbations_per_trial):
        R2, tau2 = perturb_profile(rng, t, tau_floor, R_floor)

        bf_acr_pert = brute_force_gamma_star(w, t, A0, tau2, R2)
        if bf_acr_pert is not None and (acr is None or bf_acr_pert < acr):
            soundness_violations.append(
                (n, seed, "acr", tau2, R2, bf_acr_pert, acr)
            )

        # Most-permissive tau (all zero): the mechanism-robust TCR
        # claim requires no positive activation floor at all.
        bf_tcr_pert = brute_force_gamma_star(w, t, A0, zero_tau(n), R2)
        if bf_tcr_pert is not None and (tcr is None or bf_tcr_pert < tcr):
            soundness_violations.append(
                (n, seed, "tcr", zero_tau(n), R2, bf_tcr_pert, tcr)
            )

    return tightness_mismatches, soundness_violations


def check_tightness_and_soundness(
    n_values=(3, 4, 5, 6, 7),
    trials_per_n=60,
    perturbations_per_trial=5,
    seed_base=20260721,
):
    tasks = [
        (n, trial, perturbations_per_trial, seed_base)
        for n in n_values
        for trial in range(trials_per_n)
    ]
    results = parallel_map(_check_tightness_and_soundness_one, tasks)
    total_ledgers = len(tasks)
    tightness_mismatches = [m for tm, _ in results for m in tm]
    soundness_violations = [v for _, sv in results for v in sv]
    return total_ledgers, tightness_mismatches, soundness_violations


def check_public_only_layer(n_values=(3, 5, 7), trials_per_n=20, seed_base=20260721):
    """I_pub certifies ONLY public threshold data: no resistance floor and no
    activation floor either (a missing entry contributes its trivial bound,
    zero for both -- Section 3.3). So the exact-floor profile is
    (R_i=0, tau_i=0) for every i, and both TCR and ACR must collapse to
    exactly zero, reproducing C(I_pub, A0) = 0. (random_instance's own
    randomly drawn tau is deliberately NOT used here -- using it would
    silently smuggle in a nontrivial certified activation floor, which is
    not what "public-only" means.)"""
    total = 0
    mismatches = []
    for n in n_values:
        for trial in range(trials_per_n):
            seed = deterministic_seed(n, trial, seed_base, "pub")
            w, t, A0, _, _ = random_instance(n, seed)
            zero_R = [Fr(0)] * n
            total += 1

            acr = ac_formula_gamma_star(w, t, A0, zero_tau(n), zero_R)
            tcr = ac_formula_gamma_star(w, t, A0, zero_tau(n), zero_R)
            brute = brute_force_gamma_star(w, t, A0, zero_tau(n), zero_R)
            if acr != Fr(0) or tcr != Fr(0) or brute != Fr(0):
                mismatches.append((n, seed, acr, tcr, brute))

    return total, mismatches



def check_strict_infimum_fixture():
    """Two-member ledger whose unique threshold cover contains a
    zero-resistance, positive-gate member."""
    w = [Fr(1, 2), Fr(1, 2)]
    t = Fr(1)
    A0 = set()
    tau_floor = [Fr(0), Fr(1, 2)]
    R_floor = [Fr(1), Fr(0)]
    acr = ac_formula_gamma_star(w, t, A0, tau_floor, R_floor)
    mismatches = []
    if acr != Fr(1) or floor_profile_realizable(tau_floor, R_floor):
        mismatches.append(("fixture", acr))
    epsilons = [Fr(1, 10), Fr(1, 100), Fr(1, 1000), Fr(1, 10000)]
    for eps in epsilons:
        R_eps = [Fr(1), eps]
        brute = brute_force_gamma_star(w, t, A0, tau_floor, R_eps)
        if brute != acr + eps:
            mismatches.append(("epsilon", eps, brute, acr + eps))
    return len(epsilons), mismatches

if __name__ == "__main__":
    total_ledgers, tightness_mismatches, soundness_violations = (
        check_tightness_and_soundness()
    )
    pub_total, pub_mismatches = check_public_only_layer()
    epsilon_total, strict_infimum_mismatches = check_strict_infimum_fixture()

    print(f"ledgers_tested={total_ledgers}")
    print(f"tightness_mismatches={len(tightness_mismatches)}")
    print(f"soundness_violations={len(soundness_violations)}")
    print(f"public_only_ledgers_tested={pub_total}")
    print(f"public_only_mismatches={len(pub_mismatches)}")
    print(f"strict_infimum_epsilon_profiles_tested={epsilon_total}")
    print(f"strict_infimum_mismatches={len(strict_infimum_mismatches)}")

    all_mismatches = (tightness_mismatches + soundness_violations
                      + pub_mismatches + strict_infimum_mismatches)
    if all_mismatches:
        print("\n!!! DISCREPANCY FOUND -- first 5 shown !!!")
        for m in all_mismatches[:5]:
            print(f"  {m}")
        raise SystemExit(1)

    print(
        "PASS: information_boundary_theorem -- TCR and every cap-realizable "
        "exact-floor ACR profile attained their certificates; nondegenerate "
        "and epsilon-raised profiles never beat the floor certificate. The "
        "public-only layer attained zero. A dedicated zero-resistance, "
        "positive-gate fixture confirmed a strict ACR infimum approached by "
        "four executable epsilon-profiles, matching the theorem's exact "
        "attainment criterion."
    )
