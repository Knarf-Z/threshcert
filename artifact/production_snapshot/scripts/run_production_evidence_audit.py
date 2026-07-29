#!/usr/bin/env python3
"""Audit the pinned production Keyper set and compute its evidence-supported floor.

The zero returned by this audit is a certified lower bound induced by missing
auditable evidence.  It is never interpreted as an estimate of actual member
resistance.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "shutter_keyper_snapshot.json"
PROVENANCE_PATH = ROOT / "data" / "production_keyper_set_20260613.json"
EVIDENCE_PATH = ROOT / "data" / "production_member_evidence.csv"
RESULT_JSON = ROOT / "results" / "production_evidence_audit.json"
RESULT_CSV = ROOT / "results" / "production_member_evidence_audit.csv"
CERTIFIED = "CERTIFIED"


def decimal_field(row: dict[str, str], field: str) -> Decimal:
    try:
        value = Decimal(row[field])
    except (KeyError, ArithmeticError) as error:
        raise ValueError(f"invalid decimal field {field!r}") from error
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field} must be a finite nonnegative value")
    return value


def format_decimal(value: Decimal) -> str:
    if value == value.to_integral():
        return str(value.quantize(Decimal(1)))
    return format(value.normalize(), "f")


def is_certified(row: dict[str, str], field: str) -> bool:
    return row[field].strip().upper() == CERTIFIED


def evaluate_member(row: dict[str, str]) -> dict[str, Any]:
    base_claimed = decimal_field(row, "base_resistance_floor")
    probability = decimal_field(row, "joint_enforcement_probability_floor")
    nominal_penalty = decimal_field(row, "nominal_penalty_floor")
    insurance_claimed = decimal_field(row, "insurance_or_compensation_floor")
    if probability > 1:
        raise ValueError("joint_enforcement_probability_floor cannot exceed one")

    base = (
        base_claimed
        if is_certified(row, "base_resistance_evidence_status")
        else Decimal(0)
    )
    penalty_gate = all(
        is_certified(row, field)
        for field in (
            "attribution_evidence_status",
            "forfeiture_evidence_status",
            "enforcement_evidence_status",
        )
    )
    penalty = probability * nominal_penalty if penalty_gate else Decimal(0)
    insurance_gate = all(
        is_certified(row, field)
        for field in (
            "insurance_or_compensation_evidence_status",
            "nonoverlap_evidence_status",
        )
    )
    insurance = insurance_claimed if insurance_gate else Decimal(0)
    certified_floor = base + penalty + insurance

    direct_gaps = []
    if not is_certified(row, "base_resistance_evidence_status"):
        direct_gaps.append("auditable_base_resistance_method")
    if base_claimed <= 0:
        direct_gaps.append("positive_base_resistance_floor")

    penalty_gaps = []
    if not is_certified(row, "attribution_evidence_status"):
        penalty_gaps.append("member_specific_attribution")
    if not is_certified(row, "forfeiture_evidence_status"):
        penalty_gaps.append("scope_matched_forfeiture_instrument")
    if not is_certified(row, "enforcement_evidence_status"):
        penalty_gaps.append("detection_and_execution_procedure")
    if probability <= 0:
        penalty_gaps.append("positive_joint_probability_floor")
    if nominal_penalty <= 0:
        penalty_gaps.append("positive_nominal_penalty_floor")

    activation_gaps = []
    if not is_certified(row, "activation_evidence_status"):
        activation_gaps.append("member_specific_activation_evidence")

    return {
        "member_index": int(row["member_index"]),
        "address": row["address"],
        "weight": row["weight"],
        "committee_membership_status": row["committee_membership_status"],
        "actual_resistance_status": row["actual_resistance_status"],
        "base_resistance_contribution": format_decimal(base),
        "penalty_contribution": format_decimal(penalty),
        "insurance_or_compensation_contribution": format_decimal(insurance),
        "certified_member_floor": format_decimal(certified_floor),
        "activation_branch_status": (
            "CERTIFIED" if not activation_gaps else "NOT_CERTIFIED"
        ),
        "direct_path_gap": direct_gaps,
        "penalty_path_gap": penalty_gaps,
        "activation_path_gap": activation_gaps,
        "_floor": certified_floor,
    }


def read_inputs(
    snapshot_path: Path = SNAPSHOT_PATH,
    provenance_path: Path = PROVENANCE_PATH,
    evidence_path: Path = EVIDENCE_PATH,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    with evidence_path.open(newline="", encoding="utf-8") as handle:
        evidence = list(csv.DictReader(handle))

    n = int(snapshot["committee_size"])
    q = int(snapshot["threshold_count"])
    members = snapshot["member_addresses"]
    onchain = provenance["keyper_set"]
    if not 1 <= q <= n:
        raise ValueError("threshold_count must lie between one and committee_size")
    if len(members) != n or len(evidence) != n:
        raise ValueError("snapshot, member list, and evidence ledger differ in length")
    if len({address.lower() for address in members}) != n:
        raise ValueError("member addresses must be unique")
    if int(onchain["num_members"]) != n or int(onchain["threshold"]) != q:
        raise ValueError("pinned on-chain set conflicts with snapshot dimensions")
    if [address.lower() for address in onchain["members"]] != [
        address.lower() for address in members
    ]:
        raise ValueError("pinned on-chain members conflict with snapshot")
    if provenance["audit_anchor"]["block_number"] != snapshot["archival_block_number"]:
        raise ValueError("archival block number is inconsistent")
    if provenance["audit_anchor"]["block_hash"].lower() != snapshot[
        "archival_block_hash"
    ].lower():
        raise ValueError("archival block hash is inconsistent")
    if provenance["manager"]["active_keyper_set_index"] != snapshot[
        "active_keyper_set_index"
    ]:
        raise ValueError("active Keyper-set index is inconsistent")
    if onchain["address"].lower() != snapshot["active_keyper_set_contract"].lower():
        raise ValueError("active Keyper-set address is inconsistent")

    for expected_index, (expected_address, row) in enumerate(zip(members, evidence)):
        if int(row["member_index"]) != expected_index:
            raise ValueError("member indices must be contiguous and ordered")
        if row["address"].lower() != expected_address.lower():
            raise ValueError("evidence row address conflicts with pinned member order")
        if row["committee_membership_status"] != "VERIFIED_AT_PINNED_BLOCK":
            raise ValueError("every audit row must bind committee membership")
        if row["actual_resistance_status"] != "UNKNOWN_NOT_MEASURED":
            raise ValueError("the audit must not relabel a zero floor as actual resistance")
    return snapshot, provenance, evidence


def audit_production_evidence(
    snapshot_path: Path = SNAPSHOT_PATH,
    provenance_path: Path = PROVENANCE_PATH,
    evidence_path: Path = EVIDENCE_PATH,
) -> dict[str, Any]:
    snapshot, provenance, evidence = read_inputs(
        snapshot_path, provenance_path, evidence_path
    )
    members = [evaluate_member(row) for row in evidence]
    floors = [member["_floor"] for member in members]
    n = len(floors)
    q = int(snapshot["threshold_count"])
    ordered = sorted(floors)
    certificate = sum(ordered[:q], Decimal(0))
    positive_members = sum(value > 0 for value in floors)
    minimum_positive_members = n - q + 1
    additional_positive_members = max(0, minimum_positive_members - positive_members)
    activation_evidence_members = sum(
        member["activation_branch_status"] == "CERTIFIED" for member in members
    )

    serializable_members = []
    for member in members:
        serializable_members.append(
            {key: value for key, value in member.items() if key != "_floor"}
        )

    return {
        "schema": "threshcert-production-evidence-audit-result-v1",
        "snapshot": {
            "network": snapshot["network"],
            "chain_id": snapshot["chain_id"],
            "timestamp_utc": snapshot["observation_timestamp_utc"],
            "block_number": snapshot["archival_block_number"],
            "block_hash": snapshot["archival_block_hash"],
            "keyper_set_index": snapshot["active_keyper_set_index"],
            "keyper_set_contract": snapshot["active_keyper_set_contract"],
            "committee_size": n,
            "threshold_count": q,
            "membership_records_verified": n,
            "keyper_set_added_transaction": provenance["manager"][
                "keyper_set_added_transaction"
            ],
        },
        "members": serializable_members,
        "certificate": {
            "ordered_certified_member_floors": [
                format_decimal(value) for value in ordered
            ],
            "threshold_cover_lower_bound": format_decimal(certificate),
            "status": (
                "POSITIVE_CERTIFIED"
                if certificate > 0
                else "NOT_CERTIFIED_POSITIVE_LOWER_BOUND"
            ),
            "positive_member_floors": positive_members,
            "minimum_positive_members_for_positive_certificate": minimum_positive_members,
            "additional_positive_member_floors_needed": additional_positive_members,
        },
        "activation": {
            "members_with_certified_activation_evidence": activation_evidence_members,
            "status": (
                "CERTIFIED_FOR_RECORDED_ACTIVATION_MODEL"
                if activation_evidence_members == n
                else "NOT_CERTIFIED_USE_THRESHOLD_COVER"
            ),
        },
        "evidence_gap": {
            "positive_member_path": (
                "For each selected member, either certify a positive direct resistance "
                "floor, or certify member attribution, a scope-matched forfeiture "
                "amount, and a positive joint detection-and-execution probability floor."
            ),
            "positive_certificate_count_condition": (
                f"At least {minimum_positive_members} of {n} members need strictly "
                "positive certified floors."
            ),
            "target_condition": (
                f"sum of the {q} smallest certified member floors >= B"
            ),
            "activation_upgrade": (
                "Member-specific activation evidence is additionally required before "
                "using an activation-respecting branch; otherwise the threshold-cover "
                "fallback remains the certified result."
            ),
        },
        "claim": {
            "production_certificate": "NOT_CERTIFIED",
            "actual_member_resistance": "UNKNOWN_NOT_MEASURED",
            "zero_interpretation": (
                "The certified lower bound is zero because retained auditable evidence "
                "is insufficient; actual resistance is not asserted to be zero."
            ),
            "chiado_transfer": (
                "PROHIBITED_DIFFERENT_OPERATORS_ENVIRONMENT_AND_MECHANISM"
            ),
        },
    }


def write_results(result: dict[str, Any]) -> None:
    RESULT_JSON.parent.mkdir(exist_ok=True)
    RESULT_JSON.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    fieldnames = [
        "member_index",
        "address",
        "weight",
        "committee_membership_status",
        "actual_resistance_status",
        "base_resistance_contribution",
        "penalty_contribution",
        "insurance_or_compensation_contribution",
        "certified_member_floor",
        "activation_branch_status",
        "direct_path_gap",
        "penalty_path_gap",
        "activation_path_gap",
    ]
    with RESULT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for member in result["members"]:
            row = dict(member)
            for field in (
                "direct_path_gap",
                "penalty_path_gap",
                "activation_path_gap",
            ):
                row[field] = "|".join(row[field]) or "NONE"
            writer.writerow({field: row[field] for field in fieldnames})


def print_summary(result: dict[str, Any]) -> None:
    snapshot = result["snapshot"]
    certificate = result["certificate"]
    print(f"production_audit_block={snapshot['block_number']}")
    print(f"production_audit_block_hash={snapshot['block_hash']}")
    print(f"keyper_set_index={snapshot['keyper_set_index']}")
    print(f"keyper_set_contract={snapshot['keyper_set_contract']}")
    print(
        "committee_membership_records_verified="
        f"{snapshot['membership_records_verified']}/{snapshot['committee_size']}"
    )
    print(f"threshold_count={snapshot['threshold_count']}")
    for member in result["members"]:
        print(
            f"member_{member['member_index']}={member['address']} "
            f"certified_floor={member['certified_member_floor']} "
            f"direct_path={'COMPLETE' if not member['direct_path_gap'] else 'INCOMPLETE'} "
            f"penalty_path={'COMPLETE' if not member['penalty_path_gap'] else 'INCOMPLETE'} "
            f"activation={member['activation_branch_status']}"
        )
    print(
        "ordered_certified_member_floors="
        + ",".join(certificate["ordered_certified_member_floors"])
    )
    print(
        "production_threshold_cover_lower_bound="
        + certificate["threshold_cover_lower_bound"]
    )
    print(f"production_certificate_status={certificate['status']}")
    print(f"positive_member_floors={certificate['positive_member_floors']}")
    print(
        "minimum_positive_members_for_positive_certificate="
        f"{certificate['minimum_positive_members_for_positive_certificate']}"
    )
    print(
        "additional_positive_member_floors_needed="
        f"{certificate['additional_positive_member_floors_needed']}"
    )
    print(f"activation_branch={result['activation']['status']}")
    print("actual_member_resistance=UNKNOWN_NOT_ZERO")
    print(
        "target_condition=sum_of_"
        f"{snapshot['threshold_count']}_smallest_certified_member_floors>=B"
    )
    print(f"chiado_transfer={result['claim']['chiado_transfer']}")
    print("production_evidence_audit=PASS")


def main() -> None:
    result = audit_production_evidence()
    write_results(result)
    print_summary(result)


if __name__ == "__main__":
    main()
