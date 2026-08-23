"""The two-host service as a component-contract manifest, and its mutations.

``baseline_manifest`` is the sealed model: operators produce a valid partial only
through their served route, the coordinator aggregates a threshold, and the
gateway is the sole declared producer of the usable-delivery capability. Each
mutation flips exactly one of (LC0)--(LC7), so the checker reports which way
coverage failed rather than a bare zero.
"""

from __future__ import annotations

from dataclasses import replace

from .contracts import ComponentContract, CompositionManifest, ProducerRule

CIPHERTEXT = "Ciphertext"
BUYER_REQUEST = "BuyerRequest"
BUYER_AUTH = "BuyerAuthorization"
VALID_PARTIAL = "ValidPartial"
THRESHOLD_OUTPUT = "ThresholdOutput"
IRREVERSIBLE_DEBIT = "IrreversibleDebit"
USABLE_PLAINTEXT = "UsablePlaintext"


def baseline_manifest() -> CompositionManifest:
    operators = ComponentContract(
        component_id="operators",
        input_ports=frozenset({"operator-in"}),
        output_ports=frozenset({"operator-out"}),
        producer_sites=frozenset({"POST /respond"}),
        emitting_sites=frozenset({"POST /respond"}),
        rules=(ProducerRule(VALID_PARTIAL, (CIPHERTEXT, BUYER_REQUEST), "POST /respond", external=True),),
        holds_secret=True,
        secret_external_sites=frozenset({"POST /respond"}),
        code_hash="operators@v3",
        lifecycle_fixed=True,
    )
    coordinator = ComponentContract(
        component_id="coordinator",
        input_ports=frozenset({"coordinator-in"}),
        output_ports=frozenset({"coordinator-out"}),
        producer_sites=frozenset({"aggregate"}),
        emitting_sites=frozenset({"aggregate"}),
        rules=(ProducerRule(THRESHOLD_OUTPUT, (VALID_PARTIAL,), "aggregate", external=True),),
        code_hash="coordinator@v3",
    )
    ledger = ComponentContract(
        component_id="ledger",
        output_ports=frozenset({"ledger-out"}),
        producer_sites=frozenset({"debit"}),
        emitting_sites=frozenset({"debit"}),
        rules=(ProducerRule(IRREVERSIBLE_DEBIT, (BUYER_AUTH,), "debit", external=True),),
        code_hash="ledger@v3",
    )
    gateway = ComponentContract(
        component_id="gateway",
        input_ports=frozenset({"gateway-in"}),
        output_ports=frozenset({"gateway-out"}),
        producer_sites=frozenset({"release"}),
        emitting_sites=frozenset({"release"}),
        rules=(ProducerRule(USABLE_PLAINTEXT, (THRESHOLD_OUTPUT, BUYER_AUTH), "release", external=True),),
        code_hash="gateway@v3",
    )
    return CompositionManifest(
        components=(operators, coordinator, ledger, gateway),
        port_connections=frozenset(
            {
                ("operators", "operator-out", "coordinator", "coordinator-in"),
                ("coordinator", "coordinator-out", "gateway", "gateway-in"),
                ("ledger", "ledger-out", "gateway", "gateway-in"),
            }
        ),
        cross_flows=(
            ("operators", "coordinator", "operator-out"),
            ("coordinator", "gateway", "coordinator-out"),
            ("ledger", "gateway", "ledger-out"),
        ),
        initial_capabilities=frozenset({CIPHERTEXT, BUYER_REQUEST, BUYER_AUTH}),
        root_capability=USABLE_PLAINTEXT,
        root_producer="gateway",
    )


def _swap(m: CompositionManifest, component_id: str, **changes) -> CompositionManifest:
    comps = tuple(replace(c, **changes) if c.component_id == component_id else c for c in m.components)
    return replace(m, components=comps)


# --- mutations: each flips exactly one condition ------------------------

def mutate_lc0_unruled_site(m: CompositionManifest) -> CompositionManifest:
    ops = next(c for c in m.components if c.component_id == "operators")
    return _swap(m, "operators", producer_sites=ops.producer_sites | {"POST /reshare"})


def mutate_lc1_undeclared_producer(m: CompositionManifest) -> CompositionManifest:
    ops = next(c for c in m.components if c.component_id == "operators")
    return _swap(m, "operators", emitting_sites=ops.emitting_sites | {"GET /debug/share"})


def mutate_lc2_undeclared_port(m: CompositionManifest) -> CompositionManifest:
    return replace(m, cross_flows=m.cross_flows + (("operators", "gateway", "side-channel"),))


def mutate_lc3_secret_leak(m: CompositionManifest) -> CompositionManifest:
    ops = next(c for c in m.components if c.component_id == "operators")
    return _swap(m, "operators", secret_external_sites=ops.secret_external_sites | {"GET /debug/share"})


def mutate_lc4_missing_provenance(m: CompositionManifest) -> CompositionManifest:
    gw = next(c for c in m.components if c.component_id == "gateway")
    extra = gw.rules + (ProducerRule(USABLE_PLAINTEXT, ("CachedPlaintext",), "release", external=True),)
    return _swap(m, "gateway", rules=extra)


def mutate_lc5_lifecycle(m: CompositionManifest) -> CompositionManifest:
    return _swap(m, "operators", lifecycle_fixed=False)


def mutate_lc6_cyclic(m: CompositionManifest) -> CompositionManifest:
    ops = next(c for c in m.components if c.component_id == "operators")
    # make ValidPartial depend on ThresholdOutput, which depends on ValidPartial
    cyclic = ops.rules + (ProducerRule(VALID_PARTIAL, (THRESHOLD_OUTPUT,), "POST /respond"),)
    return _swap(m, "operators", rules=cyclic)


def mutate_lc7_root_missing(m: CompositionManifest) -> CompositionManifest:
    return replace(m, root_producer=None)


def mutate_cached_output_bypass(m: CompositionManifest) -> CompositionManifest:
    """A cached-output bypass: the gateway emits the root from an undeclared cache
    site, so (LC1) fails and the checker can spell out the cheap route."""
    gw = next(c for c in m.components if c.component_id == "gateway")
    bypass = gw.rules + (ProducerRule(USABLE_PLAINTEXT, ("CachedPlaintext",), "GET /cache", external=True),)
    mutated = _swap(
        m, "gateway",
        rules=bypass,
        emitting_sites=gw.emitting_sites | {"GET /cache"},
    )
    # a cached bypass has a stale plaintext available, so CachedPlaintext is an
    # existing capability; the defect is the undeclared emitting site, not provenance
    return replace(mutated, initial_capabilities=mutated.initial_capabilities | {"CachedPlaintext"})


MUTATIONS = {
    "lc0_unruled_producer_site": (mutate_lc0_unruled_site, "LC0"),
    "lc1_undeclared_producer": (mutate_lc1_undeclared_producer, "LC1"),
    "lc2_undeclared_port": (mutate_lc2_undeclared_port, "LC2"),
    "lc3_secret_state_leak": (mutate_lc3_secret_leak, "LC3"),
    "lc4_missing_provenance": (mutate_lc4_missing_provenance, "LC4"),
    "lc5_lifecycle_upgrade": (mutate_lc5_lifecycle, "LC5"),
    "lc6_cyclic_producer": (mutate_lc6_cyclic, "LC6"),
    "lc7_root_producer_missing": (mutate_lc7_root_missing, "LC7"),
    "cached_output_bypass": (mutate_cached_output_bypass, "LC1"),
}
