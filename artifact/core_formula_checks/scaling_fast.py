"""
Faster (float-based, no Fraction overhead) scaling benchmark of the exact
subset-state activation-cover solver, mirroring the paper's own timing
table but reimplemented from scratch and run on this machine. Prints
incrementally (flush=True) so partial progress is visible even if the
whole sweep does not finish in one shot.
"""
import sys, time, random, statistics, argparse

def canonical_order_feasible_fast(S_idx, w, tau, a0_exposure):
    ordered = sorted(S_idx, key=lambda i: tau[i])
    cum = a0_exposure
    for i in ordered:
        if tau[i] > cum:
            return False
        cum += w[i]
    return True

def ac_formula_gamma_star_fast(w, t, tau, R, a0_exposure=0.0):
    m = len(w)
    U0 = list(range(m))
    best = None
    for mask in range(1, 1 << m):
        # popcount-driven weight/cost accumulation
        wsum = a0_exposure
        S = []
        mm = mask
        idx = 0
        while mm:
            if mm & 1:
                S.append(idx)
                wsum += w[idx]
            mm >>= 1
            idx += 1
        if wsum < t:
            continue
        if not canonical_order_feasible_fast(S, w, tau, a0_exposure):
            continue
        cost = sum(R[i] for i in S)
        if best is None or cost < best:
            best = cost
    return best

def random_instance(n, seed):
    rng = random.Random(seed)
    w = [1.0 / n] * n
    t = 0.5
    tau = [rng.randint(0, 99) / 100.0 * t for _ in range(n)]
    R = [float(rng.randint(1, 50)) for _ in range(n)]
    return w, t, tau, R

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", type=int, nargs="+", default=[8, 10, 12, 14])
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()

    print(f"{'n':>3} {'states':>10} {'median(s)':>12} {'min(s)':>10} {'max(s)':>10}", flush=True)
    for n in args.ns:
        times = []
        for run in range(args.runs):
            w, t, tau, R = random_instance(n, seed=20260714 + run)
            t0 = time.perf_counter()
            ac_formula_gamma_star_fast(w, t, tau, R)
            times.append(time.perf_counter() - t0)
        med = statistics.median(times)
        print(f"{n:>3} {2**n:>10,} {med:>12.6f} {min(times):>10.6f} {max(times):>10.6f}", flush=True)
