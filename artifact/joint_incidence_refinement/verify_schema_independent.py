#!/usr/bin/env python3
"""Independent finite-state checker for the declared four-of-seven schema.

This checker intentionally does not parse Solidity or import the Node checker.
It reconstructs the finite schema from the paper definition and cross-checks
the machine-readable certificate emitted by verify_refinement.mjs.
"""
from itertools import combinations, product
from json import loads
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CERTIFICATE = ROOT / "results" / "refinement_certificate.json"
MEMBERS = tuple(range(7))
Q = (2,) * 7


def admissible_credits():
    return tuple(
        y for y in product(range(3), repeat=7)
        if sum(y[:4]) <= 2 and sum(y[3:]) <= 2
    )


def quote(y, selected):
    return sum(Q[i] - y[i] for i in selected)


def main():
    credits = admissible_credits()
    terminals = tuple(combinations(MEMBERS, 4))
    assert len(credits) == 117
    assert len(terminals) == 35

    roots = {(y, False, None) for y in credits}
    terminal_states = {(y, True, selected) for y in credits for selected in terminals}
    assert len(roots) == 117
    assert len(terminal_states) == 4095
    assert roots.isdisjoint(terminal_states)

    declared_edges = {}
    payments = []
    for y in credits:
        source = (y, False, None)
        for selected in terminals:
            target = (y, True, selected)
            payment = quote(y, selected)
            key = (source, selected)
            assert key not in declared_edges
            declared_edges[key] = (target, payment)
            # Forward simulation: the offset is unchanged and the abstract
            # acquisition edge is exactly root -> selected terminal.
            assert target[0] == source[0]
            assert target[1] is True and target[2] == selected
            assert len(set(selected)) == 4
            # Payment preservation for q_i=2.
            assert payment == sum(2 - y[i] for i in selected)
            assert payment >= 4
            payments.append(payment)

    # Backward realization: every root fiber has one declared realization for
    # every abstract four-member terminal, with no duplicate target.
    assert len(declared_edges) == len(credits) * len(terminals) == 4095
    for source in roots:
        realized = {
            selected for selected in terminals
            if (source, selected) in declared_edges
        }
        assert realized == set(terminals)

    # Terminal equivalence for the declared schema.
    all_states = roots | terminal_states
    for state in all_states:
        assert (state in terminal_states) == bool(state[1])

    coordinate_minima = tuple(
        min(2 - y[i] for y in credits) for i in MEMBERS
    )
    assert coordinate_minima == (0,) * 7
    assert min(payments) == 4

    certificate = loads(CERTIFICATE.read_text(encoding="utf-8"))
    assert certificate["schema"] == "overlapping-pool-schema-certificate/v2"
    finite = certificate["finiteCheck"]
    assert finite["admissibleCreditVectors"] == len(credits)
    assert finite["terminalSets"] == len(terminals)
    assert finite["checkedStateSetPairs"] == len(declared_edges)
    assert finite["minimumResidualPayment"] == min(payments)
    assert tuple(finite["coordinateResidualMinima"]) == coordinate_minima
    assert certificate["obligations"]["implementationToSchemaBridge"].startswith("NOT_PROVED")

    print("INDEPENDENT_SCHEMA_ENTRY_CLOSURE=PASS")
    print("INDEPENDENT_SCHEMA_FORWARD_SIMULATION=PASS")
    print("INDEPENDENT_SCHEMA_BACKWARD_REALIZABILITY=PASS")
    print("INDEPENDENT_SCHEMA_TERMINAL_EQUIVALENCE=PASS")
    print("INDEPENDENT_SCHEMA_PAYMENT_PRESERVATION=PASS")
    print(f"INDEPENDENT_SCHEMA_STATE_SET_PAIRS={len(declared_edges)}")
    print(f"INDEPENDENT_SCHEMA_MIN_PAYMENT={min(payments)}")
    print("INDEPENDENT_EVM_TO_SCHEMA_BRIDGE=NOT_PROVED")


if __name__ == "__main__":
    main()