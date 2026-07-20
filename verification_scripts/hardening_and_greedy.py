"""
Independent, exhaustive verification of:
  - Theorem (Coordinated defenses can be necessary) / Corollary (Pure
    interactions of arbitrary order) -- reconstructed EXACTLY from the
    appendix proof (app:proof-coordinated-hardening), not approximated.
  - Proposition (Singleton-marginal greedy has no guarantee) -- reconstructed
    EXACTLY from the appendix proof (app:proof-singleton-greedy-no-approximation).

Unlike the paper's own reported check ("18 pure k-way constructions" /
"gain ratio ~5.0e-5" for one fixed instance), this script tests EVERY
subset A subseteq [k] exhaustively (not a sample) for several k, and
sweeps M / rho, to confirm the claimed behaviour holds everywhere it is
claimed to hold, not just at the reported operating point.
"""
import sys, os
from fractions import Fraction as Fr
from itertools import combinations
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ac_formula_gamma_star

INF = Fr(10**9)  # stand-in for "never acquirable" (tau effectively +infinity)


def coordinated_hardening_instance(k, M, A):
    """
    Exact construction from Appendix app:proof-coordinated-hardening.
    A: set of hardened entry indices (subset of range(k)).
    Returns (w, t, tau, R) over members [e_1..e_k, c, f]  (z is omitted --
    it is never acquirable under any action set, so it can never appear in
    any successful sequence and is irrelevant to Gamma*).
    """
    delta = Fr(1, 6 * k)
    t = Fr(1, 3)
    w = [delta] * k + [t - delta, t]
    R = []
    tau = []
    for j in range(k):
        if j in A:
            R.append(Fr(2 * M + 1))
            tau.append(INF)          # hardened entry: never acquirable
        else:
            R.append(Fr(1))
            tau.append(Fr(0))
    R.append(Fr(1)); tau.append(delta)         # c
    R.append(Fr(2 * M)); tau.append(Fr(0))     # f
    return w, t, tau, R


def phi(k, M, A):
    w, t, tau, R = coordinated_hardening_instance(k, M, A)
    A0 = set()
    val = ac_formula_gamma_star(w, t, A0, tau, R)
    return val


print("=== Coordinated hardening / pure Mobius interaction (exact appendix construction) ===")
all_ok = True
for k in (1, 2, 3, 4, 5, 6, 7, 8, 9):
    for M in (2, 5, 10):
        empty_val = phi(k, M, set())
        ok_empty = (empty_val == 2)
        # exhaustively check EVERY proper subset (all 2^k - 1 of them)
        proper_ok = True
        worst = None
        for size in range(0, k):  # sizes 0..k-1 are proper subsets
            for combo in combinations(range(k), size):
                v = phi(k, M, set(combo))
                if v != 2:
                    proper_ok = False
                    worst = (combo, v)
        full_val = phi(k, M, set(range(k)))
        ok_full = (full_val == 2 * M)
        status = "OK" if (ok_empty and proper_ok and ok_full) else "FAIL"
        if status == "FAIL":
            all_ok = False
        n_proper = 2**k - 1
        print(f"  k={k:2d} M={M:3d}: Phi(empty)={empty_val} (want 2) | "
              f"all {n_proper} proper subsets ->2: {proper_ok} | "
              f"Phi([k])={full_val} (want {2*M}) | ratio={full_val/empty_val if empty_val else 'NA'} "
              f"(want {M})  [{status}]" + ("" if proper_ok else f"  counterexample={worst}"))
print(f"\nAll (k,M) combinations verified with EVERY proper subset checked exhaustively: {'PASS' if all_ok else 'FAIL -- see above'}")


print("\n=== Singleton-marginal greedy has no guarantee (exact appendix construction) ===")

def singleton_greedy_instance(k, eps, X):
    """X: subset of {'d'} union {'a1',...,'ak'} deployed. Returns Phi(X)."""
    Rc = Fr(1) + (eps if 'd' in X else Fr(0))
    Ru = [Fr(1) + (Fr(1) if f'a{i+1}' in X else Fr(0)) for i in range(k)]
    return Rc + min(Ru)

def run_greedy(k, eps):
    domain = ['d'] + [f'a{i+1}' for i in range(k)]
    X = set()
    trace = []
    phi_empty = singleton_greedy_instance(k, eps, set())
    for step in range(k):  # cardinality budget k
        best_gain = None
        best_x = None
        for x in domain:
            if x in X:
                continue
            gain = singleton_greedy_instance(k, eps, X | {x}) - singleton_greedy_instance(k, eps, X)
            if best_gain is None or gain > best_gain:
                best_gain = gain
                best_x = x
        # stop if no positive marginal remains (as the paper's greedy does)
        if best_gain is not None and best_gain <= 0 and len(X) > 0:
            break
        X.add(best_x)
        trace.append((best_x, best_gain))
    return X, trace, phi_empty

all_ok2 = True
for k in (2, 3, 5, 10, 20):
    for rho_num, rho_den in [(1, 10), (1, 1000), (1, 100000)]:
        rho = Fr(rho_num, rho_den)
        eps = min(rho / 2, Fr(1, 2))
        X_greedy, trace, phi_empty = run_greedy(k, eps)
        phi_greedy = singleton_greedy_instance(k, eps, X_greedy)
        A_star = {f'a{i+1}' for i in range(k)}
        phi_star = singleton_greedy_instance(k, eps, A_star)
        num = phi_greedy - phi_empty
        den = phi_star - phi_empty
        ratio = num / den if den != 0 else None
        contains_all_a = A_star.issubset(X_greedy)
        ok = (not contains_all_a) and (ratio is not None) and (ratio < rho) and (phi_star > phi_empty)
        if not ok:
            all_ok2 = False
        print(f"  k={k:3d} rho={float(rho):.1e} eps={float(eps):.1e}: "
              f"greedy picked {trace[0][0]} first (gain={float(trace[0][1]):.1e}); "
              f"Phi(greedy)={float(phi_greedy):.4f} Phi(A*)={float(phi_star):.4f} "
              f"ratio={float(ratio):.2e} < rho? {ratio < rho}  [{'OK' if ok else 'FAIL'}]")

print(f"\nAll (k,rho) combinations verified: {'PASS' if all_ok2 else 'FAIL -- see above'}")
