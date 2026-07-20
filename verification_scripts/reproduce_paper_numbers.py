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
# 1. Activation ladder (Section 7.1.1): n=10 equal-weight, t=1/2,
#    5 cheap (R=1) + 5 seed (R=10). Cheap members require r seed
#    acquisitions first (tau_cheap = r/10, tau_seed = 0).
#    Claimed: TCR=5 (all r); ACR = 5+9r for r=0..4 -> 5,14,23,32,41
# ---------------------------------------------------------------------
print("\n=== 1. Activation ladder ===")
claimed_acr = {0: 5, 1: 14, 2: 23, 3: 32, 4: 41}
for r in range(5):
    n = 10
    w = [Fr(1, 10)] * n
    t = Fr(1, 2)
    A0 = set()
    # members 0-4 = cheap (R=1), 5-9 = seed (R=10)
    R = [Fr(1)] * 5 + [Fr(10)] * 5
    tau = [Fr(r, 10)] * 5 + [Fr(0)] * 5
    acr = ac_formula_gamma_star(w, t, A0, tau, R)
    check(f"activation-ladder ACR (r={r})", claimed_acr[r], acr)

# TCR (static threshold cover, ignoring tau) should be 5 regardless of r:
# cheapest 5 members by resistance are the 5 cheap ones (R=1 each) = 5
R_full = [Fr(1)] * 5 + [Fr(10)] * 5
tcr = sum(sorted(R_full)[:5])
check("activation-ladder TCR (all r)", 5, tcr)


# ---------------------------------------------------------------------
# 2. Mechanism stress test (Section 7.1.1): k seed members (R=1 each,
#    tau=0) + 2 core members (R=2 each) that only activate once ALL seed
#    weight is acquired. Claimed sequential cost = k+4; TCR = 4 (cores
#    alone reach threshold and are cheapest static cover).
#    Construction (derived independently to match the paper's claimed
#    numbers -- exact weights are the paper's own appendix does not
#    specify a unique instance, this is one that satisfies the stated
#    properties): t=4/5, seed total weight S=1/5 split over k seeds,
#    core weight c=2/5 each (2c=4/5=t), tau_core = S = 1/5.
# ---------------------------------------------------------------------
print("\n=== 2. Mechanism stress test (own construction matching stated properties) ===")
for k in (1, 3, 5, 8):
    n = k + 2
    S = Fr(1, 5)
    w_seed = S / k
    c = Fr(2, 5)
    t = Fr(4, 5)
    w = [w_seed] * k + [c, c]
    A0 = set()
    R = [Fr(1)] * k + [Fr(2), Fr(2)]
    tau = [Fr(0)] * k + [S, S]
    seq_cost = ac_formula_gamma_star(w, t, A0, tau, R)
    check(f"mechanism-stress sequential cost (k={k})", k + 4, seq_cost)
    # TCR: static cover ignoring tau -- brute subset search (n small)
    best_tcr = None
    for size in range(1, n + 1):
        for combo in combinations(range(n), size):
            if sum(w[i] for i in combo) >= t:
                cost = sum(R[i] for i in combo)
                if best_tcr is None or cost < best_tcr:
                    best_tcr = cost
    check(f"mechanism-stress TCR (k={k})", 4, best_tcr)


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
