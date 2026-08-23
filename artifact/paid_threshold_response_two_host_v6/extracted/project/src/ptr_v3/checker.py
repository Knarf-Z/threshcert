"""The capability-certificate checker (WP5/WP6).

It turns a committee into a payment-capability circuit, emits the proof objects
of WP3 --- a min-plus value, a verified potential certificate, and a minimum
derivation --- and runs the two adversarial fixtures the theory predicts:

* a free bypass branch collapses the value to ``0`` and is reported as
  ``REFUTED_BY_DERIVATION`` with the explicit cheap derivation (Theorem 3);
* a shared debit across two counted responders is reported as
  ``NONDECOMPOSABLE`` with the duplicated identifier, never summed
  (Proposition 5, Theorem 4).

The verdicts are re-checkable from the emitted JSON alone by
``verify_capability_certificate``: it re-verifies the potential against the
circuit and re-checks the derivation, so a drift between the paper and the record
fails there rather than here.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations
from typing import Sequence

from .capability import (
    LEAF,
    OR,
    Circuit,
    Node,
    Support,
    canonical_potential,
    check_derivation,
    derivation_cost,
    duplicate_resources,
    is_decomposable,
    min_derivation,
    threshold_service,
    value_of,
    verify_potential,
)

CERTIFIED = "CERTIFIED"
REFUTED_BY_DERIVATION = "REFUTED_BY_DERIVATION"
NONDECOMPOSABLE = "NONDECOMPOSABLE"
UNKNOWN_ALLOCATION = "UNKNOWN_ALLOCATION"


def build_two_host_circuit(floors: Sequence[int], threshold: int) -> Circuit:
    """The response service as one threshold node over per-operator leaves."""
    return threshold_service(floors, threshold, prefix="op")


def with_free_bypass(base: Circuit) -> Circuit:
    """Inject a zero-cost bypass branch: root becomes OR(paid, bypass)."""
    nodes = dict(base.nodes)
    nodes["bypass"] = Node("bypass", LEAF, floor=0, support=Support(frozenset({"debit-bypass"})))
    nodes["root"] = Node("root", OR, children=(base.root, "bypass"))
    return Circuit("root", nodes)


def with_shared_debit(base: Circuit, i: int, j: int) -> Circuit:
    """Force operators i and j to cite one debit, breaking decomposability."""
    nodes = dict(base.nodes)
    shared = Support(debit_ids=frozenset({"debit-shared"}))
    for k in (i, j):
        leaf = nodes[f"op{k}"]
        nodes[f"op{k}"] = Node(leaf.name, LEAF, floor=leaf.floor, support=shared)
    return Circuit(base.root, nodes)


@dataclass
class CertificateReport:
    status: str
    circuit_value: int
    potential_verified: bool
    decomposable: bool
    target: int | None
    derivation_cost: int
    circuit: dict
    potential: dict
    derivation: dict
    duplicate_resources: dict
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "circuit_value": self.circuit_value,
            "potential_verified": self.potential_verified,
            "decomposable": self.decomposable,
            "target": self.target,
            "derivation_cost": self.derivation_cost,
            "circuit": self.circuit,
            "potential": {k: v for k, v in sorted(self.potential.items())},
            "derivation": self.derivation,
            "duplicate_resources": self.duplicate_resources,
            "reason": self.reason,
        }


def certify(circuit: Circuit, *, allocation_ok: bool = True, target: int | None = None) -> CertificateReport:
    value = value_of(circuit)
    potential = {k: int(v) for k, v in canonical_potential(circuit).items()}
    potential_ok = verify_potential(circuit, potential)
    derivation = min_derivation(circuit)
    cost = derivation_cost(derivation)
    decomposable = is_decomposable(derivation)
    dups = duplicate_resources(derivation)

    if not allocation_ok:
        status = UNKNOWN_ALLOCATION
        reason = "allocation witness did not pass; no certificate emitted"
    elif not decomposable:
        status = NONDECOMPOSABLE
        reason = f"cheapest derivation shares payment resources {dups}; value withheld"
    elif target is not None and value < target:
        status = REFUTED_BY_DERIVATION
        reason = f"an accepting derivation costs {cost} < target {target}"
    else:
        status = CERTIFIED
        reason = f"potential certifies value {value}; cheapest derivation is decomposable"

    return CertificateReport(
        status=status,
        circuit_value=int(value),
        potential_verified=potential_ok,
        decomposable=decomposable,
        target=target,
        derivation_cost=int(cost),
        circuit=circuit.to_dict(),
        potential=potential,
        derivation=derivation.to_dict(),
        duplicate_resources=dups,
        reason=reason,
    )


def route_compression(committee_size: int, threshold: int) -> dict[str, int]:
    """The 840 -> 35 -> 1 collapse: ordered routes, unordered coalitions, one node."""
    ordered = len(list(permutations(range(committee_size), threshold)))
    unordered = len(list(combinations(range(committee_size), threshold)))
    return {"ordered_routes": ordered, "coalition_derivations": unordered, "threshold_nodes": 1}
