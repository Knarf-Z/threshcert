"""
Independent combinatorial verification for Proposition
"Certificate under partial profile-class evidence" (S5.2 of the main text).

This does NOT reimplement the paper's full evaluation pipeline; it checks
the closed-form combinatorics of TCR / ACR / MCR_{R,tau,M} against direct
brute-force enumeration, on small random instances, exactly as described
in the paper's "Verification" paragraph in S5.2.

Definitions mirror the paper exactly:
  - TCR_R(A0)            = min over threshold-reaching S of sum(R_i),
                            ignoring acquisition order entirely.
  - ACR_{R,tau}(A0)       = min over threshold-reaching, tau-order-feasible
                            S of sum(R_i), where EVERY member's tau applies.
  - MCR_{R,tau,M}(A0)     = same, but only members in M are tau-constrained;
                            members outside M are unconstrained.

Two independent feasibility checks are cross-validated against each other:
  - feasible_greedy: front-load unconstrained (non-M) members, then add
    M-members in increasing tau order, checking the running weight sum.
  - feasible_bruteforce: try every permutation of the candidate set and
    accept if any respects each M-member's tau at its position.
These agree on every trial below (0 mismatches / 3000), which is itself
evidence the greedy shortcut used inside TCR/ACR/MCR's brute-force search
is correct.

Run: python3 verify_partial_profile_evidence.py
"""
import itertools
import random
from fractions import Fraction as F

random.seed(20260721)


def feasible_greedy(S, M, tau, a0w, w):
    """Is S orderable so every i in S∩M has cumulative weight >= tau[i]
    at the moment it is added, with S\\M members unconstrained?
    Front-loading S\\M and sorting S∩M by tau ascending is always optimal
    (unconstrained members can only help meet later thresholds sooner)."""
    base = a0w + sum((w[i] for i in S if i not in M), F(0))
    constrained = sorted([i for i in S if i in M], key=lambda i: tau[i])
    cum = base
    for i in constrained:
        if cum < tau[i]:
            return False
        cum += w[i]
    return True


def feasible_bruteforce(S, M, tau, a0w, w):
    """Ground-truth check: try every permutation of S directly."""
    Sl = list(S)
    if not Sl:
        return True
    for perm in itertools.permutations(Sl):
        cum = a0w
        ok = True
        for i in perm:
            if i in M and cum < tau[i]:
                ok = False
                break
            cum += w[i]
        if ok:
            return True
    return False


def min_cost_cover(U0, w, R, a0w, t, feasible_fn):
    """Brute force over ALL subsets of U0 (2^n): minimize sum(R_i) subject
    to reaching the threshold and passing feasible_fn. Returns (cost, set)
    or (None, None) if infeasible."""
    best, best_S = None, None
    Ul = list(U0)
    n = len(Ul)
    for mask in range(1 << n):
        S = frozenset(Ul[j] for j in range(n) if (mask >> j) & 1)
        if a0w + sum((w[i] for i in S), F(0)) < t:
            continue
        if not feasible_fn(S):
            continue
        cost = sum((R[i] for i in S), F(0))
        if best is None or cost < best:
            best, best_S = cost, S
    return best, best_S


def TCR(U0, w, R, a0w, t):
    return min_cost_cover(U0, w, R, a0w, t, lambda S: True)


def ACR(U0, w, R, tau, a0w, t):
    return min_cost_cover(U0, w, R, a0w, t, lambda S: feasible_greedy(S, U0, tau, a0w, w))


def MCR(U0, w, R, tau, M, a0w, t):
    return min_cost_cover(U0, w, R, a0w, t, lambda S: feasible_greedy(S, M, tau, a0w, w))


def check_feasibility_routine(trials=3000):
    mismatches = 0
    for _ in range(trials):
        n = random.randint(1, 7)
        members = list(range(n))
        w = {i: F(random.randint(1, 9), random.randint(1, 9)) for i in members}
        tau = {i: F(random.randint(0, 20), random.randint(1, 9)) for i in members}
        a0w = F(random.randint(0, 5), random.randint(1, 9))
        M = frozenset(i for i in members if random.random() < 0.5)
        S = frozenset(i for i in members if random.random() < 0.6)
        g = feasible_greedy(S, M, tau, a0w, w)
        b = feasible_bruteforce(S, M, tau, a0w, w)
        if g != b:
            mismatches += 1
            print("MISMATCH", n, w, tau, a0w, M, S, g, b)
    print(f"[1] feasible_greedy vs feasible_bruteforce: {mismatches}/{trials} mismatches")
    assert mismatches == 0


def check_sandwich_and_boundaries(target_tested=400):
    """Draws random instances until `target_tested` of them are actually
    feasible (many random draws fail to reach the threshold at all and are
    skipped, so this loops on attempts, not on skips)."""
    bad = 0
    tested = 0
    attempts = 0
    strict_examples = []
    while tested < target_tested:
        attempts += 1
        n = random.randint(3, 6)
        U0 = list(range(n))
        w = {i: F(random.randint(1, 6), random.randint(1, 4)) for i in U0}
        R = {i: F(random.randint(0, 10)) for i in U0}
        tau = {i: F(random.randint(0, 15), random.randint(1, 4)) for i in U0}
        a0w = F(0)
        total_w = sum(w.values(), F(0))
        if total_w <= 0:
            continue
        t = total_w * F(random.randint(2, 8), 10)

        tcr, _ = TCR(U0, w, R, a0w, t)
        acr, _ = ACR(U0, w, R, tau, a0w, t)
        if tcr is None or acr is None:
            continue
        tested += 1

        M = frozenset(i for i in U0 if random.random() < 0.5)
        mcr, _ = MCR(U0, w, R, tau, M, a0w, t)
        if mcr is None:
            continue

        if not (tcr <= mcr <= acr):
            bad += 1
            print("SANDWICH VIOLATION", U0, w, R, tau, t, M, tcr, mcr, acr)
            continue

        mcr_empty, _ = MCR(U0, w, R, tau, frozenset(), a0w, t)
        mcr_full, _ = MCR(U0, w, R, tau, frozenset(U0), a0w, t)
        if mcr_empty != tcr:
            bad += 1
            print("M=EMPTY MISMATCH (should equal TCR)", mcr_empty, tcr)
        if mcr_full != acr:
            bad += 1
            print("M=U0 MISMATCH (should equal ACR)", mcr_full, acr)

        if tcr < mcr < acr:
            strict_examples.append((n, w, R, tau, t, M, tcr, mcr, acr))

    print(f"[2] TCR<=MCR<=ACR sandwich + M=empty/U0 boundary checks: "
          f"{bad} violations across {tested} feasible instances "
          f"({attempts} random draws attempted)")
    print(f"    strict-both-sides (TCR<MCR<ACR) instances found: {len(strict_examples)}")
    assert bad == 0
    return strict_examples


def check_paper_example():
    """The small, hand-verified example quoted in the main text (S5.2),
    normalized so weights sum to 1 as Section 3 requires:
    n=4, weights (1/5,2/5,1/5,1/5), threshold t=1/5, A0=empty,
    resistance (3,2,4,3), tau=(1/5,1/5,0,+infinity), M={1}.
    Expect TCR=2, ACR=4, MCR_{1}=3, strictly nested. Member 3's floor is
    represented as a large sentinel standing in for +infinity: any finite
    floor >= t is operationally identical to +infinity here, since
    achievable weight before the threshold never reaches it."""
    U0 = [0, 1, 2, 3]
    w = {0: F(1, 5), 1: F(2, 5), 2: F(1, 5), 3: F(1, 5)}
    R = {0: F(3), 1: F(2), 2: F(4), 3: F(3)}
    INF = F(10**9)
    tau = {0: F(1, 5), 1: F(1, 5), 2: F(0), 3: INF}
    a0w = F(0)
    t = F(1, 5)
    M = frozenset({1})

    tcr, tcr_S = TCR(U0, w, R, a0w, t)
    acr, acr_S = ACR(U0, w, R, tau, a0w, t)
    mcr, mcr_S = MCR(U0, w, R, tau, M, a0w, t)

    print(f"[3] Paper example: TCR={tcr} (S={set(tcr_S)}), "
          f"MCR_{{1}}={mcr} (S={set(mcr_S)}), ACR={acr} (S={set(acr_S)})")
    assert tcr == 2 and mcr == 3 and acr == 4
    assert tcr < mcr < acr


def check_shutter_counterfactual():
    """The production-audit counterfactual (S7.2): 7 equal-weight members,
    threshold 4/7, members {0,1} have (R,tau)=(4,0), members {2..6} have
    (R,tau)=(1,2/7). Expect TCR=4, ACR=10, and MCR=7 when exactly 4 of the
    5 tau=2/7 members are certified (fewer than 4 stays at TCR=4)."""
    U0 = list(range(7))
    w = {i: F(1, 7) for i in U0}
    R = {0: F(4), 1: F(4), 2: F(1), 3: F(1), 4: F(1), 5: F(1), 6: F(1)}
    tau = {0: F(0), 1: F(0), 2: F(2, 7), 3: F(2, 7), 4: F(2, 7), 5: F(2, 7), 6: F(2, 7)}
    a0w = F(0)
    t = F(4, 7)

    tcr, _ = TCR(U0, w, R, a0w, t)
    acr, _ = ACR(U0, w, R, tau, a0w, t)
    assert tcr == 4 and acr == 10

    results = {}
    for k in range(6):
        M = frozenset(range(2, 2 + k))
        mcr, _ = MCR(U0, w, R, tau, M, a0w, t)
        results[k] = mcr
    print(f"[4] Shutter counterfactual: TCR={tcr}, ACR={acr}, "
          f"MCR by count of certified tau=2/7 members: {results}")
    assert results[4] == 7
    assert all(results[k] == 4 for k in range(4))
    assert results[5] == acr


def check_remediation_monotonicity(trials=4000):
    """Proposition remediation-monotone: M1 subset M2 => MCR_M1 <= MCR_M2.
    Draws random (M1, M2) pairs with M1 subset M2 on random instances and
    checks the inequality holds in every case (treating infeasible/None as
    +infinity, which is >= any finite value)."""
    random.seed(9)
    violations = 0
    tested = 0
    for _ in range(trials):
        n = random.randint(2, 6)
        U0 = list(range(n))
        w = {i: F(random.randint(1, 6), random.randint(1, 4)) for i in U0}
        R = {i: F(random.randint(0, 10)) for i in U0}
        tau = {i: F(random.randint(0, 15), random.randint(1, 4)) for i in U0}
        a0w = F(0)
        total = sum(w.values(), F(0))
        if total <= 0:
            continue
        t = total * F(random.randint(2, 8), 10)
        M1 = frozenset(i for i in U0 if random.random() < 0.5)
        extra = [i for i in U0 if i not in M1]
        if not extra:
            continue
        M2 = M1 | frozenset(random.sample(extra, k=random.randint(1, len(extra))))
        v1, _ = MCR(U0, w, R, tau, M1, a0w, t)
        v2, _ = MCR(U0, w, R, tau, M2, a0w, t)
        if v1 is None and v2 is None:
            continue
        tested += 1
        if v1 is not None and v2 is None:
            continue  # v1 finite <= v2 = +inf: fine
        if v1 is None and v2 is not None:
            violations += 1
            print("MONOTONICITY VIOLATION (v1=inf > v2 finite)", U0, w, R, tau, t, M1, M2)
            continue
        if v1 > v2:
            violations += 1
            print("MONOTONICITY VIOLATION", U0, w, R, tau, t, M1, M2, v1, v2)
    print(f"[5] Remediation monotonicity: {tested} (M1,M2) pairs with M1 subset M2, "
          f"{violations} violations")
    assert violations == 0


def check_remediation_mobius_on_shutter_instance():
    """Verifies the pure top-order Mobius interaction claimed in the main
    text/appendix for evidence remediation: on the four-of-seven
    counterfactual, fixing any four-element subset T' of the five
    tau=2/7 members, g(A):=MCR_A - MCR_empty is 0 for every |A|<=3 and
    equals 3 for A=T' -- so every proper-subset Mobius coefficient is 0
    and mu_g(T') = g(T') = 3, exactly Corollary pure-mobius-interactions'
    phenomenon under M-certification. Also confirms (by exhaustive check
    over all C(5,k) subsets, not just nested prefixes) that every subset
    of a given size k among the five symmetric members gives the same MCR,
    so the choice of which four-element T' is immaterial."""
    U0 = list(range(7))
    w = {i: F(1, 7) for i in U0}
    R = {0: F(4), 1: F(4), 2: F(1), 3: F(1), 4: F(1), 5: F(1), 6: F(1)}
    tau = {0: F(0), 1: F(0), 2: F(2, 7), 3: F(2, 7), 4: F(2, 7), 5: F(2, 7), 6: F(2, 7)}
    a0w = F(0)
    t = F(4, 7)

    outer = [2, 3, 4, 5, 6]
    for k in range(6):
        vals = set()
        for combo in itertools.combinations(outer, k):
            cost, _ = MCR(U0, w, R, tau, frozenset(combo), a0w, t)
            vals.add(cost)
        assert len(vals) == 1, f"size-{k} subsets of the five symmetric members disagree: {vals}"

    mcr_empty, _ = MCR(U0, w, R, tau, frozenset(), a0w, t)
    Tprime = (2, 3, 4, 5)

    def g(A):
        cost, _ = MCR(U0, w, R, tau, frozenset(A), a0w, t)
        return cost - mcr_empty

    mu = {}
    for r in range(len(Tprime) + 1):
        for B in itertools.combinations(Tprime, r):
            Bs = frozenset(B)
            total = F(0)
            for r2 in range(len(Bs) + 1):
                for A in itertools.combinations(sorted(Bs), r2):
                    total += ((-1) ** (len(Bs) - len(A))) * g(frozenset(A))
            mu[Bs] = total

    proper_nonzero = [(B, v) for B, v in mu.items() if len(B) < 4 and v != 0]
    full = mu[frozenset(Tprime)]
    print(f"[6] Remediation Mobius check on four-of-seven instance: "
          f"proper-subset nonzero coefficients = {proper_nonzero}, "
          f"mu_g(full 4-set) = {full}")
    assert proper_nonzero == []
    assert full == 3


def check_LB_characterization(trials=1500):
    """Verifies the exact blocking characterization used to replace the
    withdrawn hardness sentence: MCR_M(A0) >= B  <=>  L_B \\cap F+_M(A0) is
    empty, where L_B = {S subset U0 : threshold-reaching, cost(S) < B}.
    Tested by DIRECT enumeration of L_B and of F+_M(A0)-membership (via
    feasible_greedy, independently cross-checked against feasible_bruteforce
    in check[1]) at every achievable cost boundary (each subset's own cost,
    plus a half-step above and below, to probe both sides of each possible
    B), not just one random B per instance."""
    random.seed(55)
    tested = 0
    mismatches = 0
    for _ in range(trials):
        n = random.randint(2, 5)
        U0 = list(range(n))
        w = {i: F(random.randint(1, 6), random.randint(1, 4)) for i in U0}
        R = {i: F(random.randint(0, 8)) for i in U0}
        tau = {i: F(random.randint(0, 15), random.randint(1, 4)) for i in U0}
        a0w = F(0)
        total = sum(w.values(), F(0))
        if total <= 0:
            continue
        t = total * F(random.randint(2, 8), 10)
        M = frozenset(i for i in U0 if random.random() < 0.5)

        all_subsets = [frozenset(S) for r in range(len(U0) + 1)
                       for S in itertools.combinations(U0, r)]
        all_costs = sorted(set(sum((R[i] for i in S), F(0)) for S in all_subsets))
        B_candidates = set()
        for c in all_costs:
            B_candidates.add(c)
            B_candidates.add(c + F(1, 2))
            B_candidates.add(c - F(1, 2))
        B_candidates.add(F(0))

        mcr_val, _ = MCR(U0, w, R, tau, M, a0w, t)

        for B in B_candidates:
            blocked = True  # L_B \cap F+_M(A0) == empty ?
            for S in all_subsets:
                if a0w + sum((w[i] for i in S), F(0)) < t:
                    continue  # not threshold-reaching: not in L_B
                cost = sum((R[i] for i in S), F(0))
                if cost >= B:
                    continue  # cost not < B: not in L_B
                if feasible_greedy(S, M, tau, a0w, w):
                    blocked = False
                    break
            claim_mcr_ge_B = (mcr_val is None) or (mcr_val >= B)
            tested += 1
            if claim_mcr_ge_B != blocked:
                mismatches += 1
                print("L_B CHARACTERIZATION MISMATCH", U0, w, R, tau, t, M, B,
                      "mcr=", mcr_val, "claim(mcr>=B)=", claim_mcr_ge_B,
                      "L_B blocked=", blocked)

    print(f"[7] L_B blocking characterization (MCR_M(A0)>=B <=> L_B cap "
          f"F+_M(A0)=empty): {tested} (instance,B) pairs tested, "
          f"{mismatches} mismatches")
    assert mismatches == 0


def check_binary_search_recovers_acr(trials=300):
    """Verifies the Turing-reduction claim: an oracle answering only 'is
    Remed(B) finite at zero cost?' (equivalently, via the M=U0 boundary,
    'is ACR(A0) >= B?') lets ACR(A0) be recovered EXACTLY -- including
    correctly detecting ACR(A0) = +infinity via a single preliminary
    feasibility query at B = sum(R_i)+1/D (scaled to integers), mirroring
    the two-step appendix proof exactly (feasibility query first, bounded
    binary search only once known finite), rather than assuming finiteness
    upfront the way an earlier draft of this check did. The oracle is
    implemented by calling MCR at M=U0 (=ACR) and comparing to the queried
    B; the ground-truth ACR() call is used only to check the final
    recovered value/feasibility, never inside the search itself."""
    from math import gcd

    def lcm(a, b):
        return a * b // gcd(a, b) if a and b else (a or b)

    random.seed(77)
    tested = 0
    mismatches = 0
    feasible_count = 0
    infeasible_count = 0
    for _ in range(trials):
        n = random.randint(2, 6)
        U0 = list(range(n))
        w = {i: F(random.randint(1, 6), random.randint(1, 4)) for i in U0}
        R = {i: F(random.randint(0, 12), random.randint(1, 3)) for i in U0}
        tau = {i: F(random.randint(0, 15), random.randint(1, 4)) for i in U0}
        a0w = F(0)
        total = sum(w.values(), F(0))
        if total <= 0:
            continue
        t = total * F(random.randint(2, 8), 10)

        acr_true, _ = ACR(U0, w, R, tau, a0w, t)
        tested += 1

        D = 1
        for i in U0:
            D = lcm(D, R[i].denominator)
        hi_scaled = sum((R[i] * D for i in U0), F(0))
        assert hi_scaled.denominator == 1
        hi_int = int(hi_scaled)

        def oracle(B_int, D=D):
            """Is Remed(B_int/D) finite, i.e. is ACR(A0) >= B_int/D?"""
            B = F(B_int, D)
            acr_val, _ = MCR(U0, w, R, tau, frozenset(U0), a0w, t)
            return (acr_val is None) or (acr_val >= B)

        # Step 1 (matches the appendix proof): one feasibility query one
        # unit past the maximum possible finite value -- a finite ACR can
        # never exceed sum(R_i), so this is True iff ACR(A0)=+infinity.
        if oracle(hi_int + 1):
            recovered = None
            infeasible_count += 1
        else:
            # Step 2: bounded binary search, now known to be finite.
            lo, hi = 0, hi_int
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if oracle(mid):
                    lo = mid
                else:
                    hi = mid - 1
            recovered = F(lo, D)
            feasible_count += 1

        if recovered != acr_true:
            mismatches += 1
            print("BINARY SEARCH MISMATCH", U0, w, R, tau, t,
                  "true=", acr_true, "recovered=", recovered)

    print(f"[8] Binary-search-recovers-ACR (Turing reduction check, "
          f"feasibility query + bounded search): {tested} instances "
          f"({feasible_count} feasible, {infeasible_count} infeasible, "
          f"both branches exercised), {mismatches} mismatches")
    assert mismatches == 0


def check_binary_search_infinite_resistance(trials=300):
    """Extends the Turing-reduction check to R_i = +infinity, a value the
    model explicitly allows (main text S3: R_i in [0,infinity]) but which
    the ORIGINAL query bound B = D*sum_{i in U0}(R_i)+1 silently assumed
    away: that sum is +infinity itself, not a valid integer oracle query,
    whenever any member has infinite resistance -- a real gap, flagged by
    review, in both the appendix proof and this script's own prior
    coverage (check_binary_search_recovers_acr above never generated an
    infinite R_i). The fix restricts the bound to F = {i : R_i < infinity}:
    a cover using an infinite-resistance member has infinite cost, so
    U = D*sum_{i in F}(R_i) is a valid finite upper bound on any FINITE
    ACR value regardless of how many members (if any) have R_i=infinity.
    Reuses ACR/MCR unchanged: Python's Fraction/float comparison and
    arithmetic already propagate float('inf') correctly through the
    existing cost sums and min() logic, so no separate infinity-aware
    implementation is needed -- only the query construction changes."""
    from math import gcd, inf

    def lcm(a, b):
        return a * b // gcd(a, b) if a and b else (a or b)

    random.seed(310726)
    tested = 0
    mismatches = 0
    finite_count = 0
    infinite_count = 0
    instances_with_inf_member = 0
    empty_F_count = 0
    for _ in range(trials):
        n = random.randint(2, 6)
        U0 = list(range(n))
        w = {i: F(random.randint(1, 6), random.randint(1, 4)) for i in U0}
        inf_members = frozenset(i for i in U0 if random.random() < 0.35)
        if inf_members:
            instances_with_inf_member += 1
        R = {i: (inf if i in inf_members
                 else F(random.randint(0, 12), random.randint(1, 3)))
             for i in U0}
        tau = {i: F(random.randint(0, 15), random.randint(1, 4)) for i in U0}
        a0w = F(0)
        total = sum(w.values(), F(0))
        if total <= 0:
            continue
        t = total * F(random.randint(2, 8), 10)

        acr_true, _ = ACR(U0, w, R, tau, a0w, t)
        tested += 1
        acr_is_infinite = (acr_true is None) or (acr_true == inf)

        # F = {i : R_i < infinity}; empty exactly when every member has
        # infinite resistance. D keeps its initialized value of 1 in that
        # case (the empty-LCM convention), which forces U=D*0=0 regardless
        # of D, so the convention cannot silently corrupt the query below.
        F_set = [i for i in U0 if R[i] != inf]
        if not F_set:
            empty_F_count += 1
        D = 1
        for i in F_set:
            D = lcm(D, R[i].denominator)
        U_scaled = sum((R[i] * D for i in F_set), F(0))
        assert U_scaled.denominator == 1
        U_int = int(U_scaled)

        def oracle(B_int, D=D):
            """Is Remed(B_int/D) finite, i.e. is ACR(A0) >= B_int/D?"""
            B = F(B_int, D)
            acr_val, _ = MCR(U0, w, R, tau, frozenset(U0), a0w, t)
            return (acr_val is None) or (acr_val >= B)

        # Step 1: feasibility query one unit past U, the maximum possible
        # scaled cost of any FINITE-cost cover (built only from F). True
        # iff ACR(A0) is infinite -- whether because no activation-
        # respecting threshold-reaching set exists at all, or because
        # every such set needs an infinite-resistance member.
        if oracle(U_int + 1):
            recovered_infinite = True
            recovered = None
            infinite_count += 1
        else:
            # Step 2: bounded binary search, now known to be finite.
            lo, hi = 0, U_int
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if oracle(mid):
                    lo = mid
                else:
                    hi = mid - 1
            recovered_infinite = False
            recovered = F(lo, D)
            finite_count += 1

        ok = (recovered_infinite == acr_is_infinite) and \
             (recovered_infinite or recovered == acr_true)
        if not ok:
            mismatches += 1
            print("INFINITE-RESISTANCE MISMATCH", U0, w, R, tau, t,
                  "true=", acr_true, "recovered=",
                  "+inf" if recovered_infinite else recovered)

    print(f"[9] Binary-search with some R_i=+infinity "
          f"({instances_with_inf_member}/{tested} instances had at least "
          f"one infinite-resistance member, {empty_F_count} of those had "
          f"F=empty i.e. every member infinite; {finite_count} finite-ACR, "
          f"{infinite_count} infinite-ACR outcomes recovered): "
          f"{mismatches} mismatches")
    assert mismatches == 0


def check_empty_F_convention():
    """Deterministic boundary case for the D=1-when-F=empty convention
    (flagged by review as left implicit): every member has R_i=+infinity,
    so F is empty and the LCM-of-an-empty-set convention D=1 is exercised
    directly rather than left to chance in the random trials above (which
    do hit it -- see empty_F_count in check [9] -- but not on every run,
    since it depends on the RNG draw). With F=empty, U=D*sum_{i in
    F}(R_i)=D*0=0 regardless of what D is, since w(A_0)<t is a standing
    model assumption (S3) and every nonempty threshold-reaching set here
    costs +infinity, so ACR(A_0) must be +infinity; the query at B=U+1=1
    with D=1 must detect this."""
    from math import inf

    U0 = [0, 1, 2]
    w = {0: F(1, 3), 1: F(1, 3), 2: F(1, 3)}
    R = {0: inf, 1: inf, 2: inf}
    tau = {0: F(0), 1: F(0), 2: F(0)}
    a0w = F(0)
    t = F(1, 2)

    acr_true, _ = ACR(U0, w, R, tau, a0w, t)
    F_set = [i for i in U0 if R[i] != inf]
    D = 1  # the convention under test: LCM of an empty set is 1
    U_scaled = sum((R[i] * D for i in F_set), F(0))
    assert F_set == [] and U_scaled == 0

    def oracle(B_int, D=D):
        B = F(B_int, D)
        acr_val, _ = MCR(U0, w, R, tau, frozenset(U0), a0w, t)
        return (acr_val is None) or (acr_val >= B)

    reachable_at_one = oracle(int(U_scaled) + 1)
    print(f"[10] F=empty boundary (D=1 convention): ACR_true={acr_true}, "
          f"query at B=U+1=1 reachable={reachable_at_one}")
    assert acr_true == inf
    assert reachable_at_one is True


if __name__ == "__main__":
    check_feasibility_routine(trials=3000)
    strict_examples = check_sandwich_and_boundaries(target_tested=400)
    check_paper_example()
    check_shutter_counterfactual()
    check_remediation_monotonicity(trials=4000)
    check_remediation_mobius_on_shutter_instance()
    check_LB_characterization(trials=1500)
    check_binary_search_recovers_acr(trials=300)
    check_binary_search_infinite_resistance(trials=300)
    check_empty_F_convention()
    print()
    print("All checks passed: 0 mismatches, 0 sandwich/boundary violations, "
          "strict-both-sides example confirmed, remediation monotonicity, "
          "pure Mobius interaction, L_B characterization, the "
          "binary-search/ACR Turing-reduction check, its extension to "
          "R_i=+infinity members, and the F=empty/D=1 boundary convention "
          "all confirmed.")
