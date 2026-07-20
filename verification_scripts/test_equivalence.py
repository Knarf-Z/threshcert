"""
Random cross-validation of Theorem (exact-activation-cover-frontier):
    Gamma*(A0)  ==  min_{S in T+(A0)} sum_{i in S} R_i
by comparing the brute-force sequential-search definition against the
independent subset/canonical-order (AC) formula, on many random small
instances -- not just the paper's own hand-picked examples.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import brute_force_gamma_star, ac_formula_gamma_star, random_instance

def run(n_values=(3, 4, 5, 6, 7, 8), trials_per_n=60, weight_kinds=("uniform", "random")):
    total = 0
    mismatches = []
    for n in n_values:
        for wk in weight_kinds:
            for trial in range(trials_per_n):
                seed = hash((n, wk, trial)) & 0xffffffff
                w, t, A0, tau, R = random_instance(n, seed, weight_kind=wk)
                bf = brute_force_gamma_star(w, t, A0, tau, R)
                ac = ac_formula_gamma_star(w, t, A0, tau, R)
                total += 1
                if bf != ac:
                    mismatches.append((n, wk, seed, w, t, A0, tau, R, bf, ac))
    return total, mismatches

if __name__ == "__main__":
    total, mismatches = run()
    print(f"Total random instances tested: {total}")
    print(f"Mismatches (brute-force sequence search vs AC-formula solver): {len(mismatches)}")
    if mismatches:
        print("\n!!! DISCREPANCY FOUND -- first 5 shown !!!")
        for m in mismatches[:5]:
            n, wk, seed, w, t, A0, tau, R, bf, ac = m
            print(f"  n={n} weight_kind={wk} seed={seed}")
            print(f"    w={w} t={t} A0={A0}")
            print(f"    tau={tau}")
            print(f"    R={R}")
            print(f"    brute_force={bf}  ac_formula={ac}")
    else:
        print("PASS: brute-force sequential search and the (AC) set-based formula")
        print("agree on every tested instance (uniform and non-uniform weights,")
        print("n=3..8, with and without nonempty A0).")
