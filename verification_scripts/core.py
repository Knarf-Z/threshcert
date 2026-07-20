"""
Independent, from-scratch reimplementation of the core acquisition-cost
objects defined in "Thresholds Are Not Enough" (main_text.tex), built only
from the paper's own formulas -- NOT from the authors' code (which was not
provided). Used to cross-check the paper's claimed numbers and to
random-test the central equivalence (Theorem: exact activation-cover
characterization) beyond the paper's own hand-picked examples.

All money/weight quantities are represented as exact fractions
(fractions.Fraction) wherever feasible so that "PASS/FAIL" checks are never
confused by floating-point noise.
"""
from fractions import Fraction as Fr
from itertools import permutations, combinations
import random


def to_frac_list(xs):
    return [Fr(x) for x in xs]


def brute_force_gamma_star(w, t, A0, tau, R):
    """
    Ground-truth Gamma*(A0) by literal enumeration of every ordered sequence
    of distinct members of U0 = {0,...,n-1} \\ A0, exactly as defined in
    Section 3.2 (sequential private-offer benchmark):
      - every proper prefix must have exposure < t
      - the full sequence must have exposure >= t (successful / first-crossing)
      - activation constraint tau[sigma_r] <= exposure before step r
    Cost = sum of R over the sequence. Returns None if no successful
    sequence exists (i.e. Gamma* = +infinity).
    EXPONENTIAL -- only for small instances (n - |A0| <= ~9), used purely as
    an independent ground truth to test the closed-form / set-based solver
    against.
    """
    n = len(w)
    U0 = [i for i in range(n) if i not in A0]
    a0_exposure = sum(w[i] for i in A0)
    best = None
    for k in range(1, len(U0) + 1):
        for subset in combinations(U0, k):
            for perm in permutations(subset):
                exposure = a0_exposure
                feasible = True
                for r, member in enumerate(perm):
                    # activation constraint: tau[member] <= exposure so far
                    if tau[member] > exposure:
                        feasible = False
                        break
                    exposure += w[member]
                    # every proper prefix (r < len-1) must remain sub-threshold
                    if r < len(perm) - 1 and exposure >= t:
                        feasible = False
                        break
                if not feasible:
                    continue
                if exposure < t:
                    continue  # never reached threshold -> not successful
                cost = sum(R[i] for i in perm)
                if best is None or cost < best:
                    best = cost
    return best


def canonical_order_feasible(S, w, t, A0, tau):
    """
    Checks S subseteq U0 is 'auxiliary-buildable' (in F+(A0)) via the
    canonical nondecreasing-tau order (Proposition: canonical activation
    order). Returns True/False. This does NOT require S to be
    threshold-reaching -- that is checked separately.
    """
    a0_exposure = sum(w[i] for i in A0)
    ordered = sorted(S, key=lambda i: tau[i])
    cum = a0_exposure
    for i in ordered:
        if tau[i] > cum:
            return False
        cum += w[i]
    return True


def ac_formula_gamma_star(w, t, A0, tau, R):
    """
    Independent implementation of the (AC) reduction in
    Theorem: exact-activation-cover-frontier --
      Gamma*(A0) = min over S in T+(A0) of sum_{i in S} R_i
    where T+(A0) = {S in F+(A0) : w(A0)+w(S) >= t}.
    Brute subset-state search over all S subseteq U0 (2^|U0|), exactly
    matching the paper's own stated O(m 2^m) complexity claim.
    Returns None if T+(A0) is empty (Gamma* = +infinity).
    """
    n = len(w)
    U0 = [i for i in range(n) if i not in A0]
    a0_exposure = sum(w[i] for i in A0)
    best = None
    m = len(U0)
    for mask in range(1, 1 << m):
        S = [U0[j] for j in range(m) if (mask >> j) & 1]
        if a0_exposure + sum(w[i] for i in S) < t:
            continue
        if not canonical_order_feasible(S, w, t, A0, tau):
            continue
        cost = sum(R[i] for i in S)
        if best is None or cost < best:
            best = cost
    return best


def uniform_lower_tail(n, e, t, caps, R_remaining_sorted):
    """
    Proposition: uniform sequential acquisition cost.
    w_i = 1/n for all i, e = |A0|, q = ceil(n*t) - e.
    caps: function r -> c_r = v((e+r-1)/n) for r=1..q (already evaluated,
    list indexed from r=1).
    R_remaining_sorted: sorted list of the n-e remaining resistances,
    ascending, R^{U0}_(1) <= ... <= R^{U0}_(n-e).
    Returns the closed-form Gamma*(A0), or None (+infinity) if any of the
    first q order statistics exceeds its cap.
    """
    import math
    q = math.ceil(n * t) - e
    if q <= 0:
        return Fr(0)
    if q > len(R_remaining_sorted):
        return None
    for r in range(1, q + 1):
        if R_remaining_sorted[r - 1] > caps[r - 1]:
            return None
    return sum(R_remaining_sorted[:q])


def random_instance(n, seed, weight_kind="uniform"):
    """
    Generate a random small instance with EXACT (Fraction) parameters:
    weights, threshold t in (0,1), initial set A0 with w(A0) < t, per-member
    tau_i in [0, t) (activation thresholds), and per-member resistance R_i.
    """
    rng = random.Random(seed)
    if weight_kind == "uniform":
        w = [Fr(1, n) for _ in range(n)]
    else:
        raw = [rng.randint(1, 9) for _ in range(n)]
        s = sum(raw)
        w = [Fr(x, s) for x in raw]

    t = Fr(rng.randint(5, 15), 20)  # threshold strictly between 0.25 and 0.75

    # A0: random subset with total weight < t
    A0 = set()
    idx = list(range(n))
    rng.shuffle(idx)
    cum = Fr(0)
    for i in idx:
        if rng.random() < 0.3 and cum + w[i] < t:
            A0.add(i)
            cum += w[i]

    # tau_i drawn uniformly in [0, t) as a fraction of t, so exposure sufficiency
    # domain [0,t) is respected by construction
    tau = [Fr(rng.randint(0, 99), 100) * t for _ in range(n)]

    R = [Fr(rng.randint(0, 50)) for _ in range(n)]
    return w, t, A0, tau, R
