"""
Independently reproduce the specific named numbers in Section 7 (Evaluation)
of the paper, using the from-scratch solver in core.py -- built purely from
the paper's own formulas/definitions, not from the authors' (unseen) code.

Each check prints CLAIMED (from the paper text) vs COMPUTED (from this
independent implementation) and a clear MATCH / MISMATCH verdict.
"""
import sys, os
from fractions import Fraction as Fr
from itertools import combinations, product
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ac_formula_gamma_star, canonical_order_feasible

RESULTS = []

def check(name, claimed, computed):
    ok = (claimed == computed)
    RESULTS.append((name, claimed, computed, ok))
    print(f"[{'MATCH' if ok else 'MISMATCH!!'}] {name}: claimed={claimed}  computed={computed}")
    return ok


# ---------------------------------------------------------------------
# 1. Equal-cost weighted activation check (conference appendix):
#    all seven member floors are one. Two 1/14-weight prerequisite members
#    are initially operational; every other member has gate 1/7.
#    The gap is two extra acquisitions, not a higher-priced-first order.
# ---------------------------------------------------------------------
print("\n=== 1. Equal-cost weighted activation check ===")
w = [Fr(2, 7), Fr(2, 7), Fr(2, 21), Fr(2, 21), Fr(2, 21), Fr(1, 14), Fr(1, 14)]
t = Fr(4, 7)
A0 = set()
R = [Fr(1)] * 7
tau = [Fr(1, 7)] * 5 + [Fr(0), Fr(0)]
acr = ac_formula_gamma_star(w, t, A0, tau, R)
check("equal-cost weighted ACR", 4, acr)
best_tcr = min(
    sum(R[i] for i in combo)
    for size in range(1, 8)
    for combo in combinations(range(7), size)
    if sum(w[i] for i in combo) >= t
)
check("equal-cost weighted TCR", 2, best_tcr)


# ---------------------------------------------------------------------
# 2. Fixed-uniform-cost mechanism stress test (Theorem 5(ii), Lambda=0):
#    k prerequisite seeds and two cores all have unit cost. The seed total
#    weight is delta; each core has weight (1-delta)/2 and gate delta.
#    Sequential cost is k+2 and static/package threshold cost is 2.
# ---------------------------------------------------------------------
print("\n=== 2. Fixed-uniform-cost mechanism stress test ===")
for k in (1, 3, 5, 8):
    n = k + 2
    delta = Fr(1, 4)
    w_seed = delta / k
    core_weight = (1 - delta) / 2
    t = 1 - delta
    w = [w_seed] * k + [core_weight, core_weight]
    A0 = set()
    R = [Fr(1)] * n
    tau = [Fr(0)] * k + [delta, delta]
    seq_cost = ac_formula_gamma_star(w, t, A0, tau, R)
    check(f"mechanism-stress sequential cost (k={k})", k + 2, seq_cost)
    best_tcr = min(
        sum(R[i] for i in combo)
        for size in range(1, n + 1)
        for combo in combinations(range(n), size)
        if sum(w[i] for i in combo) >= t
    )
    check(f"mechanism-stress TCR (k={k})", 2, best_tcr)


# ---------------------------------------------------------------------
# 3. Defense allocation (Appendix app:bottleneck-hardening-check): EXACT
#    published construction (not reconstructed) -- 6 bottleneck members
#    b1..b6 (R=2, w=0.08 each), 2 decoys d1,d2 (R=0.5, w=0.26 each),
#    t=0.24, 4 minimal covers {b1,b2,b3},{b1,b4,b5},{b2,b4,b6},{b3,b5,b6}.
# ---------------------------------------------------------------------
print("\n=== 3. Defensive allocation (exact published instance) ===")
covers = [(0, 1, 2), (0, 3, 4), (1, 3, 5), (2, 4, 5)]  # indices into b1..b6 (0-5)
base_R = [Fr(2)] * 6              # b1..b6
order = ['d1', 'd2', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6']

def cover_cost(hb):
    return min(sum(base_R[i] + hb[i] for i in c) for c in covers)

budgets = [0, 2, 4, 6, 8, 10]
claimed = {
    0: (6, 6, 6), 2: (6, 6, 7), 4: (6, 6, 8),
    6: (6, 7, 9), 8: (7, 9, 10), 10: (9, 9, 11),
}

# --- cheapest-current-resistance rule ---
def cheapest_resistance_rule(H):
    hd = {'d1': Fr(0), 'd2': Fr(0)}
    hb = [Fr(0)] * 6
    Rd = {'d1': Fr('0.5'), 'd2': Fr('0.5')}
    for _ in range(H):
        cur = {'d1': Rd['d1'] + hd['d1'], 'd2': Rd['d2'] + hd['d2']}
        for i in range(6):
            cur[f'b{i+1}'] = base_R[i] + hb[i]
        best_name = min(order, key=lambda name: (cur[name], order.index(name)))
        if best_name in hd:
            hd[best_name] += 1
        else:
            hb[order.index(best_name) - 2] += 1
    return cover_cost(hb)

# --- weight-order cycling rule ---
def weight_cycle_rule(H):
    hb = [Fr(0)] * 6
    for u in range(H):
        name = order[u % 8]
        if name.startswith('b'):
            hb[order.index(name) - 2] += 1
    return cover_cost(hb)

# --- bottleneck (exact optimum) rule: enumerate all integer splits of H
#     over the 6 bottleneck members (decoys provably never help, since
#     they are not in any minimal cover) ---
def bottleneck_optimum(H):
    best = None
    # stars-and-bars enumeration of h1..h6 >=0 summing to <=H
    def gen(remaining, k):
        if k == 1:
            yield (remaining,)
            return
        for x in range(remaining + 1):
            for rest in gen(remaining - x, k - 1):
                yield (x,) + rest
    for total_used in range(H + 1):
        for combo in gen(total_used, 6):
            hb = [Fr(x) for x in combo]
            val = cover_cost(hb)
            if best is None or val > best:
                best = val
    return best

for H in budgets:
    cr = cheapest_resistance_rule(H)
    wc = weight_cycle_rule(H)
    bo = bottleneck_optimum(H)
    c_cr, c_wc, c_bo = claimed[H]
    check(f"defense-alloc H={H} cheapest-resistance", c_cr, cr)
    check(f"defense-alloc H={H} weight-cycle", c_wc, wc)
    check(f"defense-alloc H={H} bottleneck-optimum", c_bo, bo)


# ---------------------------------------------------------------------
# 4. Baseline comparison (Appendix app:extended-baselines), heavy-lower-
#    tail four-of-seven profile: resistances (1,3,6,8,11,16,25), q=4.
#    Claimed: public-only=0, global-member-floor=4, exact-lower-tail=18,
#    mean-heuristic=40.
# ---------------------------------------------------------------------
print("\n=== 4. Baseline comparison (heavy-lower-tail 4-of-7) ===")
Rs = [Fr(1), Fr(3), Fr(6), Fr(8), Fr(11), Fr(16), Fr(25)]
q = 4
public_only = 0
global_member_floor = q * min(Rs)
exact_lower_tail = sum(sorted(Rs)[:q])
mean_heuristic = q * (sum(Rs) / len(Rs))
check("baseline public-only", 0, public_only)
check("baseline global-member-floor", 4, global_member_floor)
check("baseline exact-lower-tail", 18, exact_lower_tail)
check("baseline mean-heuristic", 40, mean_heuristic)


# ---------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------
print("\n" + "=" * 60)
n_ok = sum(1 for r in RESULTS if r[3])
print(f"TOTAL CHECKS: {len(RESULTS)}   MATCH: {n_ok}   MISMATCH: {len(RESULTS)-n_ok}")
if n_ok != len(RESULTS):
    print("\nMISMATCHES:")
    for name, c, comp, ok in RESULTS:
        if not ok:
            print(f"  {name}: claimed={c} computed={comp}")
