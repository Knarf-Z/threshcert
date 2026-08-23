"""The payment-capability circuit --- the object WP3's Theorems 2--4 are about.

A finite, acyclic circuit over typed capabilities. Leaves carry a payment floor
and a payment support (disjoint-checkable identifier sets); internal nodes are
OR, AND, or a weighted threshold THR. The module is deliberately network-free: it
computes the min-plus value, verifies a potential certificate, builds and checks
a capability derivation (a proof tree), and enforces payment decomposability.
Everything here is a direct executable image of the theory:

* ``circuit_value``            -- the recursion of WP3 Definition (circuit value).
* ``verify_potential``         -- one direction of WP3 Theorem 3 (duality).
* ``min_derivation`` / ``derivation_cost`` -- the min-cost proof tree, the other.
* ``is_decomposable``          -- WP3 Definition (payment decomposability).
* ``unique_resource_cost``     -- the shared-resource cost of WP3 Theorem 4.
* ``set_cover_circuit`` / ``min_unique_cover_cost`` -- the Theorem 4 reduction.

The separation between ``derivation_cost`` (additive) and
``unique_resource_cost`` (shared paid once) is the whole point of
WP3 Proposition 5: they agree exactly on decomposable derivations and can diverge
otherwise, which is why a certificate is only sound with a decomposability
witness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable, Mapping, Sequence

LEAF = "LEAF"
OR = "OR"
AND = "AND"
THR = "THR"

INF = float("inf")


@dataclass(frozen=True)
class Support:
    """A leaf's payment support: the identifiers WP3 requires to be disjoint."""

    debit_ids: frozenset[str] = frozenset()
    refund_ids: frozenset[str] = frozenset()
    funding_ids: frozenset[str] = frozenset()

    def disjoint(self, other: "Support") -> bool:
        return (
            self.debit_ids.isdisjoint(other.debit_ids)
            and self.refund_ids.isdisjoint(other.refund_ids)
            and self.funding_ids.isdisjoint(other.funding_ids)
        )

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "debit_ids": sorted(self.debit_ids),
            "refund_ids": sorted(self.refund_ids),
            "funding_ids": sorted(self.funding_ids),
        }


@dataclass(frozen=True)
class Node:
    name: str
    kind: str
    children: tuple[str, ...] = ()
    # LEAF only:
    floor: int = 0
    support: Support = field(default_factory=Support)
    # THR only:
    weights: tuple[int, ...] = ()
    threshold: int = 0

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"name": self.name, "kind": self.kind}
        if self.kind == LEAF:
            d["floor"] = self.floor
            d["support"] = self.support.to_dict()
        else:
            d["children"] = list(self.children)
        if self.kind == THR:
            d["weights"] = list(self.weights)
            d["threshold"] = self.threshold
        return d


@dataclass
class Circuit:
    root: str
    nodes: dict[str, Node]

    def node(self, name: str) -> Node:
        return self.nodes[name]

    # --- structure -------------------------------------------------------
    def topological_order(self) -> list[str]:
        """Children-before-parents order; raises on a cycle (WP3 acyclicity)."""
        order: list[str] = []
        state: dict[str, int] = {}  # 0=visiting, 1=done

        def visit(name: str) -> None:
            s = state.get(name)
            if s == 1:
                return
            if s == 0:
                raise ValueError(f"capability circuit is cyclic at {name!r}")
            state[name] = 0
            for c in self.nodes[name].children:
                if c not in self.nodes:
                    raise ValueError(f"node {name!r} references unknown child {c!r}")
                visit(c)
            state[name] = 1
            order.append(name)

        visit(self.root)
        return order

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "payment_capability_circuit",
            "root": self.root,
            "nodes": [self.nodes[n].to_dict() for n in sorted(self.nodes)],
        }


def _qualifying_subsets(weights: Sequence[int], threshold: int, k: int) -> Iterable[tuple[int, ...]]:
    for size in range(1, k + 1):
        for idx in combinations(range(k), size):
            if sum(weights[i] for i in idx) >= threshold:
                yield idx


# --- value (WP3 Definition) ---------------------------------------------

def circuit_value(circuit: Circuit) -> dict[str, float]:
    """Least-fixed-point min-plus value over an acyclic circuit."""
    value: dict[str, float] = {}
    for name in circuit.topological_order():
        node = circuit.nodes[name]
        if node.kind == LEAF:
            value[name] = node.floor
        elif node.kind == OR:
            value[name] = min((value[c] for c in node.children), default=INF)
        elif node.kind == AND:
            value[name] = sum(value[c] for c in node.children)
        elif node.kind == THR:
            best = INF
            for idx in _qualifying_subsets(node.weights, node.threshold, len(node.children)):
                best = min(best, sum(value[node.children[i]] for i in idx))
            value[name] = best
        else:
            raise ValueError(f"unknown node kind {node.kind!r}")
    return value


def value_of(circuit: Circuit) -> float:
    return circuit_value(circuit)[circuit.root]


# --- potential certificate (WP3 Theorem 3, verifier direction) ----------

def verify_potential(circuit: Circuit, z: Mapping[str, float]) -> bool:
    """True iff ``z`` satisfies every local inequality of WP3 Theorem 3.

    A verifier that accepts a potential with ``z[root] >= g`` thereby certifies
    ``Val(root) >= g`` without recomputing the circuit --- the positive
    certificate the duality promises.
    """
    for name, node in circuit.nodes.items():
        if name not in z:
            return False
        zv = z[name]
        if node.kind == LEAF:
            if zv > node.floor:
                return False
        elif node.kind == OR:
            if any(zv > z[c] for c in node.children):
                return False
        elif node.kind == AND:
            if zv > sum(z[c] for c in node.children):
                return False
        elif node.kind == THR:
            for idx in _qualifying_subsets(node.weights, node.threshold, len(node.children)):
                if zv > sum(z[node.children[i]] for i in idx):
                    return False
        else:
            return False
    return True


def canonical_potential(circuit: Circuit) -> dict[str, float]:
    """The tight potential ``z = Val``; feasible by Bellman optimality."""
    return circuit_value(circuit)


# --- derivations (the proof-tree side of WP3 Theorem 3) -----------------

@dataclass
class Derivation:
    """A proof tree: at each node, which rule/branch was taken to the leaves."""

    name: str
    kind: str
    children: tuple["Derivation", ...] = ()
    floor: int = 0
    support: Support = field(default_factory=Support)

    def leaves(self) -> list["Derivation"]:
        if self.kind == LEAF:
            return [self]
        out: list[Derivation] = []
        for c in self.children:
            out.extend(c.leaves())
        return out

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"name": self.name, "kind": self.kind}
        if self.kind == LEAF:
            d["floor"] = self.floor
            d["support"] = self.support.to_dict()
        else:
            d["children"] = [c.to_dict() for c in self.children]
        return d


def min_derivation(circuit: Circuit) -> Derivation:
    """The cheapest accepting derivation under the additive (decomposable) cost."""
    value = circuit_value(circuit)

    def build(name: str) -> Derivation:
        node = circuit.nodes[name]
        if node.kind == LEAF:
            return Derivation(name, LEAF, floor=node.floor, support=node.support)
        if node.kind == OR:
            best = min(node.children, key=lambda c: value[c])
            return Derivation(name, OR, children=(build(best),))
        if node.kind == AND:
            return Derivation(name, AND, children=tuple(build(c) for c in node.children))
        if node.kind == THR:
            best_idx: tuple[int, ...] = ()
            best_cost = INF
            for idx in _qualifying_subsets(node.weights, node.threshold, len(node.children)):
                cost = sum(value[node.children[i]] for i in idx)
                if cost < best_cost:
                    best_cost, best_idx = cost, idx
            return Derivation(name, THR, children=tuple(build(node.children[i]) for i in best_idx))
        raise ValueError(f"unknown node kind {node.kind!r}")

    return build(circuit.root)


def derivation_cost(d: Derivation) -> int:
    """Additive cost: the sum of the floors of the selected leaves."""
    return sum(leaf.floor for leaf in d.leaves())


def check_derivation(circuit: Circuit, d: Derivation) -> bool:
    """True iff ``d`` is a structurally valid accepting derivation of the root."""

    def ok(name: str, node_d: Derivation) -> bool:
        if name != node_d.name or name not in circuit.nodes:
            return False
        node = circuit.nodes[name]
        if node.kind != node_d.kind:
            return False
        if node.kind == LEAF:
            return node_d.floor == node.floor and node_d.support == node.support
        if node.kind == OR:
            if len(node_d.children) != 1:
                return False
            c = node_d.children[0]
            return c.name in node.children and ok(c.name, c)
        if node.kind == AND:
            if len(node_d.children) != len(node.children):
                return False
            return all(cd.name == cn and ok(cn, cd) for cn, cd in zip(node.children, node_d.children))
        if node.kind == THR:
            chosen = tuple(cd.name for cd in node_d.children)
            if len(set(chosen)) != len(chosen):
                return False
            pos = {cn: i for i, cn in enumerate(node.children)}
            if any(cn not in pos for cn in chosen):
                return False
            if sum(node.weights[pos[cn]] for cn in chosen) < node.threshold:
                return False
            return all(ok(cd.name, cd) for cd in node_d.children)
        return False

    return ok(d.name, d)


# --- decomposability (WP3 Definition and Proposition 5) -----------------

def is_decomposable(d: Derivation) -> bool:
    """Pairwise-disjoint supports across the selected leaves."""
    leaves = d.leaves()
    for i in range(len(leaves)):
        for j in range(i + 1, len(leaves)):
            if not leaves[i].support.disjoint(leaves[j].support):
                return False
    return True


def duplicate_resources(d: Derivation) -> dict[str, list[str]]:
    """Identifiers that appear in more than one selected leaf (the witness of
    non-decomposability that a NONDECOMPOSABLE verdict should carry)."""
    seen: dict[str, list[str]] = {}
    resources = (
        ("debit_ids", lambda leaf: leaf.support.debit_ids),
        ("refund_ids", lambda leaf: leaf.support.refund_ids),
        ("funding_ids", lambda leaf: leaf.support.funding_ids),
    )
    for kind, select in resources:
        counts: dict[str, int] = {}
        for leaf in d.leaves():
            for rid in select(leaf):
                counts[rid] = counts.get(rid, 0) + 1
        dup = sorted(r for r, n in counts.items() if n > 1)
        if dup:
            seen[kind] = dup
    return seen


def unique_resource_cost(d: Derivation, resource_price: Mapping[str, int]) -> int:
    """WP3 Theorem 4 cost: each distinct debit resource paid exactly once."""
    ids: set[str] = set()
    for leaf in d.leaves():
        ids |= leaf.support.debit_ids
    return sum(resource_price[i] for i in ids)


# --- the Theorem 4 reduction (set cover) --------------------------------

def set_cover_circuit(universe: Sequence[int], sets: Sequence[Sequence[int]]) -> tuple[Circuit, dict[str, int]]:
    """Depth-two AND/OR circuit whose min unique-resource cost is min set cover.

    Each set becomes a unit-cost leaf sharing one debit resource; each element is
    an OR over the sets containing it; the root is the AND over all elements.
    """
    nodes: dict[str, Node] = {}
    resource_price: dict[str, int] = {}
    for j, _members in enumerate(sets):
        rid = f"r{j}"
        resource_price[rid] = 1
        nodes[f"x{j}"] = Node(f"x{j}", LEAF, floor=1, support=Support(debit_ids=frozenset({rid})))
    for u in universe:
        covering = tuple(f"x{j}" for j, s in enumerate(sets) if u in s)
        nodes[f"v{u}"] = Node(f"v{u}", OR, children=covering)
    nodes["root"] = Node("root", AND, children=tuple(f"v{u}" for u in universe))
    return Circuit("root", nodes), resource_price


def min_unique_cover_cost(universe: Sequence[int], sets: Sequence[Sequence[int]]) -> int:
    """Brute-force minimum set-cover size, for validating small fixtures."""
    idx = range(len(sets))
    for size in range(1, len(sets) + 1):
        for choice in combinations(idx, size):
            covered: set[int] = set()
            for j in choice:
                covered |= set(sets[j])
            if set(universe) <= covered:
                return size
    raise ValueError("universe is not coverable by the given sets")


# --- convenience constructors -------------------------------------------

def threshold_service(floors: Sequence[int], threshold: int, *, prefix: str = "op") -> Circuit:
    """The q-of-n response service: a single THR node over unit-weight leaves,
    each leaf carrying its own distinct debit so a clean run is decomposable."""
    n = len(floors)
    nodes: dict[str, Node] = {}
    children: list[str] = []
    for i, p in enumerate(floors, start=1):
        name = f"{prefix}{i}"
        nodes[name] = Node(name, LEAF, floor=p, support=Support(debit_ids=frozenset({f"debit-{name}"})))
        children.append(name)
    nodes["u"] = Node("u", THR, children=tuple(children), weights=(1,) * n, threshold=threshold)
    return Circuit("u", nodes)
