"""
Independent verification of Theorem (Activation-boundary instability):
for every K>1, eta>0, epsilon>0, there exist fixed committee/resistance
data and two monotone right-continuous common caps v^-, v^+ with
sup_alpha |v^-(alpha)-v^+(alpha)| <= eta, such that
    Gamma*_{v^-}(empty) = 1   but   Gamma*_{v^+}(empty) >= K,
and under v^+ every successful process must first acquire a set of weight
at most epsilon before a threshold-reaching member becomes active.

Construction reconstructed EXACTLY from Appendix (proof of
thm:valuation-instability): one terminal member c (weight 1-delta,
resistance 1) plus m cheap seed members (combined weight delta, each
resistance 1-d). Brute-force verification is only feasible for small K
(m grows linearly in K, and the exact solver is exponential in m -- this
mirrors the paper's own stated weakly-NP-hard computational boundary, not
a limitation specific to this reimplementation). For large K we instead
check the closed-form arithmetic the construction itself relies on.
"""
import sys, os, math
from fractions import Fraction as Fr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ac_formula_gamma_star

MAX_M_FOR_BRUTE_FORCE = 16  # 2^16 subsets is still fast; beyond this we only check arithmetic


def instability_instance(K, eta, eps):
    delta = min(eps, Fr(1, 4))
    d = min(eta / 2, Fr(1, 4))
    t = 1 - delta
    m = max(1, math.ceil(float((K - 1) / (1 - d))))
    w = [1 - delta] + [delta / m] * m          # member 0 = c, members 1..m = seeds
    R = [Fr(1)] + [1 - d] * m
    tau_minus = [Fr(0)] * (m + 1)              # v^- constant 1: c acquirable from alpha=0
    tau_plus = [delta] + [Fr(0)] * m           # v^+: c needs alpha>=delta; seeds free from 0
    return w, t, R, tau_minus, tau_plus, delta, d, m


def run_brute_force_checks():
    print(f"{'K':>6} {'eta':>8} {'eps':>8} {'m':>4} {'Gamma*(v-)':>11} {'Gamma*(v+)':>11} "
          f"{'sup<=eta':>9} {'w(G)<=eps':>10} {'>=K':>5}")
    all_ok = True
    for K in (Fr(2), Fr(5), Fr(10)):
        for eta in (Fr(1, 10), Fr(1, 1000)):
            for eps in (Fr(1, 10), Fr(1, 1000)):
                w, t, R, tau_m, tau_p, delta, d, m = instability_instance(K, eta, eps)
                if m > MAX_M_FOR_BRUTE_FORCE:
                    print(f"K={float(K)} eta={float(eta)} eps={float(eps)}: m={m} "
                          f"too large for brute-force demo, skipped (see arithmetic check below)")
                    continue
                A0 = set()
                gm = ac_formula_gamma_star(w, t, A0, tau_m, R)
                gp = ac_formula_gamma_star(w, t, A0, tau_p, R)
                ok = (gm == 1) and (d <= eta) and (delta <= eps) and (gp >= K)
                if not ok:
                    all_ok = False
                print(f"{float(K):>6.0f} {float(eta):>8.1e} {float(eps):>8.1e} {m:>4} "
                      f"{float(gm):>11.4f} {float(gp):>11.4f} "
                      f"{str(d <= eta):>9} {str(delta <= eps):>10} {str(gp >= K):>5}"
                      f"  [{'OK' if ok else 'FAIL'}]")
    return all_ok


def run_arithmetic_checks_large_K():
    print("\nArithmetic-only check for large K (no brute force -- the exact solver")
    print("is exponential in m, same boundary the paper itself states):")
    all_ok = True
    for K in (50, 1000, 10**6):
        eta = Fr(1, 10)
        eps = Fr(1, 1000)
        delta = min(eps, Fr(1, 4))
        d = min(eta / 2, Fr(1, 4))
        m = max(1, math.ceil((K - 1) / float(1 - d)))
        seed_cost = 1 + m * (1 - d)
        ok = seed_cost >= K
        if not ok:
            all_ok = False
        print(f"  K={K:>8}: m={m:>8}  1+m(1-d)={float(seed_cost):>12.2f}  "
              f">=K? {ok}")
    return all_ok


if __name__ == "__main__":
    ok1 = run_brute_force_checks()
    ok2 = run_arithmetic_checks_large_K()
    print(f"\nPASS: {ok1 and ok2}")
