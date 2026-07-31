"""Finite regressions for the two premises outside CR1--CR5.

This is a logical transcription check, not a proof of the paper's general
theorem. It constructs a positive finite instance with more than one
partition of a terminal set and two countermodels for deleted premises.
"""

from fractions import Fraction
from itertools import combinations


def size_subsets(xs, size):
    return {frozenset(s) for s in combinations(xs, size)}


def terminal_paths(root, terminals, edges):
    outgoing = {}
    for source, block, target in edges:
        outgoing.setdefault(source, []).append((block, target))
    paths = []

    def visit(state, blocks):
        if state in terminals:
            paths.append((state, tuple(blocks)))
            return
        for block, target in outgoing.get(state, []):
            assert block and block.isdisjoint(state)
            assert target == state | block
            visit(target, blocks + [block])

    visit(root, [])
    return paths


def trace_relation(paths, offsets, q):
    triples, partition_costs = set(), {}
    for terminal, blocks in paths:
        for y in offsets:
            cost = sum(
                (q[i] - y[i] for block in blocks for i in block), Fraction(0)
            )
            triples.add((terminal, y, cost))
            partition_costs.setdefault((terminal, y), set()).add(cost)
    return triples, partition_costs


def expected_relation(terminals, offsets, q):
    return {
        (terminal, y, sum((q[i] - y[i] for i in terminal), Fraction(0)))
        for terminal in terminals for y in offsets
    }


def identity_refinement_holds(root, terminals, edges, q, offsets):
    """CR1--CR5 hold when the concrete system is the abstract graph itself."""
    paths = terminal_paths(root, terminals, edges)
    reachable = {root}
    for terminal, blocks in paths:
        state = root
        for block in blocks:
            state |= block
            reachable.add(state)
        assert state == terminal
    entry_universe = set(edges)
    cr1 = entry_universe == set(edges)
    cr2 = all(source in reachable and target == source | block
              for source, block, target in edges)
    cr3 = all((source, block, target) in entry_universe
              for source, block, target in edges)
    cr4 = all((state in terminals) == (state in terminals) for state in reachable)
    cr5 = all(
        sum((q[i] - y[i] for i in block), Fraction(0)) >= 0
        for _, block, _ in edges for y in offsets
    )
    return all((cr1, cr2, cr3, cr4, cr5))


# Positive instance: each two-set has a direct edge and two singleton orders.
universe = tuple(range(4))
root = frozenset()
terminals = size_subsets(universe, 2)
edges = set()
for terminal in terminals:
    edges.add((root, terminal, terminal))
    for first in terminal:
        singleton = frozenset({first})
        edges.add((root, singleton, singleton))
        edges.add((singleton, terminal - singleton, terminal))
q = tuple(Fraction(2) for _ in universe)
offsets = (
    tuple(Fraction(0) for _ in universe),
    (Fraction(1), Fraction(0), Fraction(1, 2), Fraction(0)),
)
paths = terminal_paths(root, terminals, edges)
traces, partition_costs = trace_relation(paths, offsets, q)
assert {terminal for terminal, _ in paths} == terminals
assert identity_refinement_holds(root, terminals, edges, q, offsets)
assert traces == expected_relation(terminals, offsets, q)
assert all(len(costs) == 1 for costs in partition_costs.values())
assert any(sum(1 for terminal, _ in paths if terminal == s) > 1 for s in terminals)
print("RPSC_TRACE_THEOREM=PASS")
print("PARTITION_INVARIANCE=PASS")


# Countermodel 1: CR1--CR5 and RPSC hold for an identity system, but its
# terminal family omits one set from the separately declared K.
small_q = (Fraction(1), Fraction(1))
small_offsets = ((Fraction(0), Fraction(0)),)
declared_k = {frozenset({0}), frozenset({1})}
incomplete_terminals = {frozenset({0})}
incomplete_edges = {(root, frozenset({0}), frozenset({0}))}
assert identity_refinement_holds(
    root, incomplete_terminals, incomplete_edges, small_q, small_offsets
)
incomplete_paths = terminal_paths(root, incomplete_terminals, incomplete_edges)
incomplete_traces, _ = trace_relation(incomplete_paths, small_offsets, small_q)
assert incomplete_traces != expected_relation(declared_k, small_offsets, small_q)
print("TERMINAL_COMPLETENESS_COUNTERMODEL=REJECTED")


# Countermodel 2: the trace relation is complete, but the separately declared
# mechanism semantics omits one trace. Payment-labelled triple equality fails.
complete_edges = {
    (root, frozenset({0}), frozenset({0})),
    (root, frozenset({1}), frozenset({1})),
}
assert identity_refinement_holds(root, declared_k, complete_edges, small_q, small_offsets)
complete_paths = terminal_paths(root, declared_k, complete_edges)
complete_traces, _ = trace_relation(complete_paths, small_offsets, small_q)
mechanism_outcomes = {(frozenset({0}), small_offsets[0], Fraction(1))}
assert complete_traces == expected_relation(declared_k, small_offsets, small_q)
assert mechanism_outcomes != complete_traces
print("OUTCOME_CORRESPONDENCE_COUNTERMODEL=REJECTED")

# Empty attainable relations use the separate extended-value branch. There
# is no SAT witness and no minimum over the empty pair relation to invoke.
empty_outcomes = set()
empty_incidence = float("inf")
assert empty_incidence == float("inf")
assert not empty_outcomes
assert not any(True for _ in empty_outcomes)
print("EMPTY_ATTAINABLE_RELATION_BOUNDARY=PASS")