"""Sealed-composition checker: Theorem 5 (LC0--LC7) as an executable object.

This is the experimental instantiation of the sealed-composition theorem. It
models the two-host service as a set of component contracts joined by declared
typed ports, and checks each local condition (LC0)--(LC7) as a real predicate over
that model rather than as a coverage flag. A clean model reports ``SEALED``; a
model that violates any condition reports ``COVERAGE_NOT_ESTABLISHED`` naming the
condition, and where the violation actually yields a delivery route, an explicit
counter-derivation.

Each mutation in :mod:`ptr_exp` flips exactly one condition, so the checker
distinguishes the seven ways coverage can fail rather than collapsing them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence

SEALED = "SEALED"
COVERAGE_NOT_ESTABLISHED = "COVERAGE_NOT_ESTABLISHED"


@dataclass(frozen=True)
class ProducerRule:
    """A declared rule ``inputs => output`` fired at ``site`` in a component."""

    output: str
    inputs: tuple[str, ...]
    site: str
    external: bool = False  # produces a capability visible outside the component


@dataclass(frozen=True)
class ComponentContract:
    component_id: str
    input_ports: frozenset[str] = field(default_factory=frozenset)
    output_ports: frozenset[str] = field(default_factory=frozenset)
    producer_sites: frozenset[str] = field(default_factory=frozenset)
    # Every code site that can emit a capability-bearing output. (LC1) needs
    # emitting_sites subset of producer_sites.
    emitting_sites: frozenset[str] = field(default_factory=frozenset)
    rules: tuple[ProducerRule, ...] = ()
    holds_secret: bool = False
    # Sites through which secret-bearing state can reach an external capability.
    # (LC3) needs these subset of producer_sites.
    secret_external_sites: frozenset[str] = field(default_factory=frozenset)
    code_hash: str = ""
    lifecycle_fixed: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "input_ports": sorted(self.input_ports),
            "output_ports": sorted(self.output_ports),
            "producer_sites": sorted(self.producer_sites),
            "emitting_sites": sorted(self.emitting_sites),
            "rules": [
                {"output": r.output, "inputs": list(r.inputs), "site": r.site, "external": r.external}
                for r in self.rules
            ],
            "holds_secret": self.holds_secret,
            "secret_external_sites": sorted(self.secret_external_sites),
            "code_hash": self.code_hash,
            "lifecycle_fixed": self.lifecycle_fixed,
        }


@dataclass(frozen=True)
class CompositionManifest:
    components: tuple[ComponentContract, ...]
    # Declared typed channels: (from_component, from_output_port, to_component, to_input_port).
    port_connections: frozenset[tuple[str, str, str, str]] = field(default_factory=frozenset)
    # Actual cross-component capability flows observed: (from_component, to_component, port).
    cross_flows: tuple[tuple[str, str, str], ...] = ()
    initial_capabilities: frozenset[str] = field(default_factory=frozenset)
    root_capability: str = ""
    root_producer: str | None = None  # component id declaring a rule producing the root

    def to_dict(self) -> dict[str, object]:
        return {
            "components": [c.to_dict() for c in self.components],
            "port_connections": sorted(list(p) for p in self.port_connections),
            "cross_flows": [list(f) for f in self.cross_flows],
            "initial_capabilities": sorted(self.initial_capabilities),
            "root_capability": self.root_capability,
            "root_producer": self.root_producer,
        }


@dataclass
class CompositionReport:
    status: str
    violations: list[dict[str, object]]
    counter_derivation: list[str] | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "violations": self.violations,
            "counter_derivation": self.counter_derivation,
        }


def _all_rules(m: CompositionManifest) -> list[tuple[ComponentContract, ProducerRule]]:
    return [(c, r) for c in m.components for r in c.rules]


def _counter_derivation(m: CompositionManifest, undeclared_site: str) -> list[str] | None:
    """If an undeclared/bypass site produces the root, spell out the cheap route."""
    for c in m.components:
        for r in c.rules:
            if r.output == m.root_capability and r.site == undeclared_site:
                return [f"{c.component_id}:{r.site}", f"=> {r.output}", "(via undeclared/bypass site)"]
    return None


def verify_composition(m: CompositionManifest) -> CompositionReport:
    violations: list[dict[str, object]] = []
    counter: list[str] | None = None

    def fail(lc: str, detail: str) -> None:
        violations.append({"condition": lc, "detail": detail})

    caps = set(m.initial_capabilities)
    for _, r in _all_rules(m):
        caps.add(r.output)
        caps.update(r.inputs)

    # (LC0) producer-rule soundness: every producer site carries a rule.
    for c in m.components:
        ruled = {r.site for r in c.rules}
        missing = sorted(c.producer_sites - ruled)
        if missing:
            fail("LC0", f"{c.component_id} has producer sites without a rule: {missing}")

    # (LC1) producer completeness: every emitting site is a declared producer.
    for c in m.components:
        undeclared = sorted(c.emitting_sites - c.producer_sites)
        if undeclared:
            fail("LC1", f"{c.component_id} emits from undeclared sites: {undeclared}")
            counter = counter or _counter_derivation(m, undeclared[0])

    # (LC2) port closure: every cross-component flow uses a declared channel.
    declared = {(a, c) for (a, _ap, c, _cp) in m.port_connections}
    for (frm, to, port) in m.cross_flows:
        if (frm, to) not in declared:
            fail("LC2", f"cross-component flow {frm}->{to} over undeclared port {port!r}")

    # (LC3) state confinement: secret state escapes only through declared producers.
    for c in m.components:
        if c.holds_secret:
            leak = sorted(c.secret_external_sites - c.producer_sites)
            if leak:
                fail("LC3", f"{c.component_id} leaks secret state through undeclared sites: {leak}")

    # (LC4) input provenance: every rule input is initial or produced somewhere.
    produced = {r.output for _, r in _all_rules(m)} | set(m.initial_capabilities)
    for c, r in _all_rules(m):
        orphan = [i for i in r.inputs if i not in produced]
        if orphan:
            fail("LC4", f"{c.component_id}:{r.site} consumes unproduced capabilities {orphan}")

    # (LC5) lifecycle closure: every component's code is fixed for the claim window.
    for c in m.components:
        if not c.lifecycle_fixed:
            fail("LC5", f"{c.component_id} code hash is not fixed for the claim interval")

    # (LC6) well-founded production: the capability dependency graph is acyclic.
    edges: dict[str, set[str]] = {}
    for _, r in _all_rules(m):
        edges.setdefault(r.output, set()).update(r.inputs)
    state: dict[str, int] = {}
    cyclic: list[str] = []

    def visit(cap: str) -> None:
        s = state.get(cap)
        if s == 1:
            return
        if s == 0:
            cyclic.append(cap)
            return
        state[cap] = 0
        for dep in edges.get(cap, ()):  # dependencies
            visit(dep)
        state[cap] = 1

    for cap in list(edges):
        visit(cap)
    if cyclic:
        fail("LC6", f"capability production is cyclic at {sorted(set(cyclic))}")

    # (LC7) root adequacy: the root capability has a declared root producer.
    root_rules = [
        r for c in m.components for r in c.rules
        if r.output == m.root_capability and c.component_id == m.root_producer
    ]
    if m.root_producer is None or not root_rules:
        fail("LC7", f"the root capability {m.root_capability!r} has no declared root producer")

    status = SEALED if not violations else COVERAGE_NOT_ESTABLISHED
    return CompositionReport(status=status, violations=violations, counter_derivation=counter)
