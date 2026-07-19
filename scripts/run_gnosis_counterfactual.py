#!/usr/bin/env python3
"""Run the deterministic counterfactual on the pinned Gnosis committee geometry.

The fixture changes no production record and uses no chain write.  Its
resistance and activation floors are explicit hypothetical inputs that exercise
the public, threshold-cover, activation-cover, and robust-fallback branches of
the same exact solver used by the other controlled experiments.
"""
from __future__ import annotations

import json
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, Sequence

from defense_lattice import (
    SequentialInstance,
    StepCap,
    exact_minimum_sequential_solution,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "gnosis_counterfactual_fixture.json"
RESULT_PATH = ROOT / "results" / "gnosis_counterfactual_result.json"


def parse_fraction(value: object) -> Fraction:
    if isinstance(value, bool):
        raise ValueError("booleans are not rational inputs")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value)
    raise ValueError(f"unsupported rational input: {value!r}")


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def load_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_pinned_geometry(fixture: dict[str, Any]) -> dict[str, Any]:
    geometry = fixture["production_geometry"]
    provenance_path = ROOT / geometry["source"]
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    anchor = provenance["audit_anchor"]
    keyper_set = provenance["keyper_set"]

    checks = {
        "snapshot_time_utc": anchor["timestamp_utc"],
        "archival_block_number": anchor["block_number"],
        "archival_block_hash": anchor["block_hash"],
        "keyper_set_index": keyper_set["index"],
        "keyper_set_contract": keyper_set["address"],
        "committee_size": keyper_set["num_members"],
        "threshold_count": keyper_set["threshold"],
    }
    for field, recorded in checks.items():
        declared = geometry[field]
        if isinstance(recorded, str) and recorded.startswith("0x"):
            matches = str(declared).lower() == recorded.lower()
        else:
            matches = declared == recorded
        if not matches:
            raise ValueError(
                f"counterfactual geometry mismatch for {field}: "
                f"fixture={declared!r}, provenance={recorded!r}"
            )

    if len(keyper_set["members"]) != geometry["committee_size"]:
        raise ValueError("pinned member count does not match committee geometry")
    if not keyper_set["finalized"]:
        raise ValueError("pinned Keyper set is not finalized")
    return provenance


def threshold_cover_solution(
    resistances: Sequence[Fraction], threshold_count: int
) -> tuple[Fraction, tuple[int, ...]]:
    if not 1 <= threshold_count <= len(resistances):
        raise ValueError("invalid threshold count")
    cover = tuple(
        sorted(range(len(resistances)), key=lambda member: (resistances[member], member))[
            :threshold_count
        ]
    )
    return sum((resistances[member] for member in cover), Fraction(0)), cover


def activation_instance(
    weights: Sequence[Fraction],
    resistances: Sequence[Fraction],
    activation_floors: Sequence[Fraction],
    threshold: Fraction,
    initial_exposure: Fraction,
) -> SequentialInstance:
    if not (len(weights) == len(resistances) == len(activation_floors)):
        raise ValueError("counterfactual vectors must have equal length")

    caps: list[StepCap] = []
    for resistance, activation_floor in zip(resistances, activation_floors):
        if resistance <= 0:
            raise ValueError("counterfactual resistance floors must be positive")
        if activation_floor < 0:
            raise ValueError("activation floors must be nonnegative")
        if activation_floor == 0:
            caps.append(StepCap(((Fraction(0), resistance),)))
        else:
            caps.append(
                StepCap(
                    (
                        (Fraction(0), Fraction(0)),
                        (activation_floor, resistance),
                    )
                )
            )

    return SequentialInstance(
        weights=tuple(weights),
        resistances=tuple(resistances),
        caps=tuple(caps),
        threshold=threshold,
        initial_exposure=initial_exposure,
    )


def select_certified_branch(
    threshold_cover: Fraction,
    activation_cover: Fraction,
    gates: dict[str, bool],
) -> dict[str, object]:
    activation_gate = (
        gates["ordered_witness_certified"]
        and gates["exposure_sufficiency_certified"]
    )
    if activation_gate:
        return {
            "selected_branch": "ACTIVATION_COVER",
            "certificate": format_fraction(activation_cover),
            "activation_certificate_emitted": True,
        }
    if gates["separable_payment_lower_bounds_certified"]:
        return {
            "selected_branch": "ROBUST_THRESHOLD_COVER_FALLBACK",
            "certificate": format_fraction(threshold_cover),
            "activation_certificate_emitted": False,
        }
    return {
        "selected_branch": "PUBLIC_ONLY_FALLBACK",
        "certificate": "0",
        "activation_certificate_emitted": False,
    }


def solve_profile(
    weights: Sequence[Fraction],
    resistances: Sequence[Fraction],
    activation_floors: Sequence[Fraction],
    threshold: Fraction,
    threshold_count: int,
    initial_exposure: Fraction,
) -> dict[str, object]:
    tc_cost, tc_cover = threshold_cover_solution(resistances, threshold_count)
    solution = exact_minimum_sequential_solution(
        activation_instance(
            weights,
            resistances,
            activation_floors,
            threshold,
            initial_exposure,
        )
    )
    if solution is None:
        raise AssertionError("the counterfactual activation profile must be feasible")
    return {
        "threshold_cover": tc_cost,
        "threshold_cover_members": tc_cover,
        "activation_cover": solution.cost,
        "activation_witness": solution.witness,
        "activation_member_mask": solution.member_mask,
    }


def counterfactual_vectors_for_seeds(
    seed_members: Sequence[int], committee_size: int
) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
    seeds = set(seed_members)
    if len(seeds) != 2 or any(member not in range(committee_size) for member in seeds):
        raise ValueError("exactly two distinct seed members are required")
    resistances = tuple(
        Fraction(4) if member in seeds else Fraction(1)
        for member in range(committee_size)
    )
    activations = tuple(
        Fraction(0) if member in seeds else Fraction(2, 7)
        for member in range(committee_size)
    )
    return resistances, activations


def evaluate_counterfactual(fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    fixture = load_fixture() if fixture is None else fixture
    provenance = validate_pinned_geometry(fixture)
    geometry = fixture["production_geometry"]
    inputs = fixture["counterfactual_inputs"]

    weights = tuple(parse_fraction(value) for value in inputs["weights"])
    resistances = tuple(
        parse_fraction(value) for value in inputs["resistance_floors"]
    )
    activation_floors = tuple(
        parse_fraction(value) for value in inputs["activation_floors"]
    )
    threshold = parse_fraction(geometry["threshold"])
    initial_exposure = parse_fraction(geometry["initial_exposure"])
    threshold_count = int(geometry["threshold_count"])

    base = solve_profile(
        weights,
        resistances,
        activation_floors,
        threshold,
        threshold_count,
        initial_exposure,
    )

    accepted = select_certified_branch(
        base["threshold_cover"],
        base["activation_cover"],
        dict(fixture["certificate_gates"]),
    )
    rejected_gates = dict(fixture["certificate_gates"])
    rejected_gates["ordered_witness_certified"] = False
    rejected_gates["exposure_sufficiency_certified"] = False
    rejected = select_certified_branch(
        base["threshold_cover"],
        base["activation_cover"],
        rejected_gates,
    )

    placement_rows: list[dict[str, object]] = []
    for seed_members in combinations(range(len(weights)), 2):
        variant_resistances, variant_activations = counterfactual_vectors_for_seeds(
            seed_members, len(weights)
        )
        variant = solve_profile(
            weights,
            variant_resistances,
            variant_activations,
            threshold,
            threshold_count,
            initial_exposure,
        )
        placement_rows.append(
            {
                "seed_members": list(seed_members),
                "threshold_cover": format_fraction(variant["threshold_cover"]),
                "activation_cover": format_fraction(variant["activation_cover"]),
                "activation_witness": list(variant["activation_witness"]),
            }
        )

    gate_rows: list[dict[str, object]] = []
    for gate_name in (
        "ordered_witness_certified",
        "exposure_sufficiency_certified",
    ):
        gates = dict(fixture["certificate_gates"])
        gates[gate_name] = False
        selected = select_certified_branch(
            base["threshold_cover"], base["activation_cover"], gates
        )
        gate_rows.append({"disabled_gate": gate_name, **selected})

    placements_pass = all(
        row["threshold_cover"] == "4" and row["activation_cover"] == "10"
        for row in placement_rows
    )
    gates_pass = all(
        row["selected_branch"] == "ROBUST_THRESHOLD_COVER_FALLBACK"
        and row["certificate"] == "4"
        and not row["activation_certificate_emitted"]
        for row in gate_rows
    )

    return {
        "schema": "threshcert-gnosis-counterfactual-result-v1",
        "classification": fixture["classification"],
        "pinned_geometry": {
            "archival_block_number": geometry["archival_block_number"],
            "archival_block_hash": geometry["archival_block_hash"],
            "keyper_set_index": geometry["keyper_set_index"],
            "keyper_set_contract": geometry["keyper_set_contract"],
            "committee_size": geometry["committee_size"],
            "threshold": geometry["threshold"],
            "member_count_verified": len(provenance["keyper_set"]["members"]),
        },
        "counterfactual_inputs": inputs,
        "branches": {
            "public_ledger": {
                "certificate": "0",
                "uses_hypothetical_member_floors": False,
            },
            "resistance_only_threshold_cover": {
                "certificate": format_fraction(base["threshold_cover"]),
                "cover": list(base["threshold_cover_members"]),
            },
            "activation_cover": {
                "certificate": format_fraction(base["activation_cover"]),
                "witness": list(base["activation_witness"]),
                "member_mask": base["activation_member_mask"],
                **accepted,
            },
            "activation_gate_rejected_robust_fallback": {
                "gate_values": rejected_gates,
                "threshold_cover_witness": list(base["threshold_cover_members"]),
                **rejected,
            },
        },
        "regression_checks": {
            "seed_member_placements_checked": len(placement_rows),
            "seed_member_placements": placement_rows,
            "all_seed_placements_tc_4_ac_10": placements_pass,
            "gate_disable_cases": gate_rows,
            "all_activation_gate_failures_fall_back_to_4": gates_pass,
        },
        "claim_boundary": {
            **fixture["claim_boundary"],
            "allowed_description": fixture["classification"],
            "forbidden_descriptions": [
                "Gnosis activation experiment",
                "production validation",
                "measured Keyper resistance",
            ],
        },
    }


def write_result(result: dict[str, Any], path: Path = RESULT_PATH) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(
        (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )


def main() -> None:
    result = evaluate_counterfactual()
    write_result(result)
    branches = result["branches"]
    regressions = result["regression_checks"]
    print("counterfactual_classification=" + result["classification"])
    print("counterfactual_ledger=" + result["counterfactual_inputs"]["ledger"])
    print("cost_units=" + result["counterfactual_inputs"]["cost_units"])
    print("public_certificate=" + branches["public_ledger"]["certificate"])
    print(
        "resistance_only_TC="
        + branches["resistance_only_threshold_cover"]["certificate"]
    )
    print(
        "TC_cover="
        + ",".join(
            map(str, branches["resistance_only_threshold_cover"]["cover"])
        )
    )
    print("activation_AC=" + branches["activation_cover"]["certificate"])
    print(
        "AC_witness="
        + ",".join(map(str, branches["activation_cover"]["witness"]))
    )
    print(
        "activation_gate_rejected_certificate="
        + branches["activation_gate_rejected_robust_fallback"]["certificate"]
    )
    print(
        "activation_gate_rejected_branch="
        + branches["activation_gate_rejected_robust_fallback"]["selected_branch"]
    )
    print(
        "seed_position_choices="
        + str(regressions["seed_member_placements_checked"])
    )
    print(
        "seed_position_regression="
        + ("PASS" if regressions["all_seed_placements_tc_4_ac_10"] else "FAIL")
    )
    print(
        "activation_gate_fallback_regression="
        + (
            "PASS"
            if regressions["all_activation_gate_failures_fall_back_to_4"]
            else "FAIL"
        )
    )
    print("claim_boundary=HYPOTHETICAL_FLOORS_NOT_PRODUCTION_EVIDENCE")


if __name__ == "__main__":
    main()
