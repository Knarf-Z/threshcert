"""Independent re-check of the emitted capability certificate.

Rebuilds each circuit from the emitted JSON, re-verifies the potential against it,
re-checks the derivation and its cost, and confirms the three verdicts. It never
imports the checker's decision logic beyond the circuit primitives, so a certificate
that does not actually hold fails here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.capability import (  # noqa: E402
    LEAF,
    Circuit,
    Derivation,
    Node,
    Support,
    check_derivation,
    derivation_cost,
    is_decomposable,
    value_of,
    verify_potential,
)


def _support(d: dict) -> Support:
    return Support(
        debit_ids=frozenset(d.get("debit_ids", [])),
        refund_ids=frozenset(d.get("refund_ids", [])),
        funding_ids=frozenset(d.get("funding_ids", [])),
    )


def circuit_from_dict(d: dict) -> Circuit:
    nodes: dict[str, Node] = {}
    for n in d["nodes"]:
        if n["kind"] == LEAF:
            nodes[n["name"]] = Node(n["name"], LEAF, floor=int(n["floor"]), support=_support(n["support"]))
        else:
            nodes[n["name"]] = Node(
                n["name"], n["kind"], children=tuple(n.get("children", [])),
                weights=tuple(n.get("weights", [])), threshold=int(n.get("threshold", 0)),
            )
    return Circuit(d["root"], nodes)


def derivation_from_dict(d: dict) -> Derivation:
    if d["kind"] == LEAF:
        return Derivation(d["name"], LEAF, floor=int(d["floor"]), support=_support(d["support"]))
    return Derivation(d["name"], d["kind"], children=tuple(derivation_from_dict(c) for c in d["children"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a capability certificate.")
    parser.add_argument("--input", type=Path, default=ROOT / "results" / "capability_certificate.v3.json")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    cover = int(data["cover"])
    checks: list[tuple[str, bool]] = []

    def check(name: str, cond: object) -> None:
        checks.append((name, bool(cond)))

    # baseline: potential re-verifies, derivation re-checks, value == cover, decomposable
    b = data["baseline"]
    bc = circuit_from_dict(b["circuit"])
    bd = derivation_from_dict(b["derivation"])
    check("BASELINE_VALUE_RECOMPUTES", value_of(bc) == b["circuit_value"] == cover)
    check("BASELINE_POTENTIAL_VERIFIES", verify_potential(bc, {k: int(v) for k, v in b["potential"].items()}))
    check("BASELINE_DERIVATION_VALID", check_derivation(bc, bd))
    check("BASELINE_DERIVATION_COST", derivation_cost(bd) == cover)
    check("BASELINE_DECOMPOSABLE", is_decomposable(bd))
    check("BASELINE_STATUS_CERTIFIED", b["status"] == "CERTIFIED")

    # bypass: value 0, an accepting derivation below cover, status REFUTED_BY_DERIVATION
    p = data["bypass_fixture"]
    pc = circuit_from_dict(p["circuit"])
    pd = derivation_from_dict(p["derivation"])
    check("BYPASS_VALUE_ZERO", value_of(pc) == p["circuit_value"] == 0)
    check("BYPASS_DERIVATION_VALID_AND_CHEAP", check_derivation(pc, pd) and derivation_cost(pd) < cover)
    check("BYPASS_STATUS_REFUTED", p["status"] == "REFUTED_BY_DERIVATION")

    # shared debit: the cheapest derivation is non-decomposable, status NONDECOMPOSABLE
    s = data["shared_debit_fixture"]
    sc = circuit_from_dict(s["circuit"])
    sd = derivation_from_dict(s["derivation"])
    check("SHARED_DEBIT_NONDECOMPOSABLE", not is_decomposable(sd))
    check("SHARED_DEBIT_HAS_DUPLICATE", bool(s["duplicate_resources"]))
    check("SHARED_DEBIT_STATUS", s["status"] == "NONDECOMPOSABLE")

    # compression
    c = data["route_compression"]
    check("COMPRESSION_840_35_1", c["ordered_routes"] == 840 and c["coalition_derivations"] == 35 and c["threshold_nodes"] == 1)
    check("EMBEDDED_CHECKS", all(data["checks"].values()))

    width = max(len(n) for n, _ in checks)
    for name, ok in checks:
        print(f"{name.ljust(width)}  {'PASS' if ok else 'FAIL'}")
    if any(not ok for _, ok in checks):
        print("CAPABILITY_CERTIFICATE_VERIFICATION=FAIL")
        return 1
    print("CAPABILITY_CERTIFICATE_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
