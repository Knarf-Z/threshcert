#!/usr/bin/env python3
"""Deterministic experiment for incentive-compatible floor admission.

The verifier never treats a reported reservation price as evidence.  It
recomputes a member-borne loss floor from enforceable collateral and certified
upper bounds on recovery and third-party reimbursement.  Missing scope,
ownership, forfeiture, offset, or validity evidence fails closed to zero.
"""
from __future__ import annotations

import json
import random
from copy import deepcopy
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "floor_admission_experiment.json"
NOW = 1_800_000_000
THRESHOLD = 4


@dataclass(frozen=True)
class FloorRecord:
    member: int
    reported_floor: int
    locked_member_collateral: int = 0
    max_recovery: int = 0
    max_external_reimbursement: int = 0
    signer_bound: bool = False
    member_ownership_bound: bool = False
    automatic_forfeiture: bool = False
    offset_cap_certified: bool = False
    code_hash_bound: bool = False
    valid_from: int = 0
    valid_until: int = 0
    revoked: bool = False


def admit_floor(record: FloorRecord, now: int = NOW) -> tuple[int, list[str]]:
    failures: list[str] = []
    checks = {
        "SIGNER_BINDING_MISSING": record.signer_bound,
        "MEMBER_OWNERSHIP_MISSING": record.member_ownership_bound,
        "AUTOMATIC_FORFEITURE_MISSING": record.automatic_forfeiture,
        "OFFSET_CAP_MISSING": record.offset_cap_certified,
        "CODE_HASH_BINDING_MISSING": record.code_hash_bound,
        "NOT_YET_VALID": record.valid_from <= now,
        "EXPIRED": now <= record.valid_until,
        "REVOKED": not record.revoked,
    }
    failures.extend(name for name, passed in checks.items() if not passed)
    if failures:
        return 0, failures
    admitted = max(
        0,
        record.locked_member_collateral
        - record.max_recovery
        - record.max_external_reimbursement,
    )
    return admitted, []


def threshold_certificate(records: list[FloorRecord]) -> tuple[int, list[int]]:
    floors = sorted(admit_floor(record)[0] for record in records)
    return sum(floors[:THRESHOLD]), floors


def complete_record(member: int, net_floor: int, report: int | None = None) -> FloorRecord:
    recovery = 1
    reimbursement = 1
    return FloorRecord(
        member=member,
        reported_floor=report if report is not None else net_floor,
        locked_member_collateral=net_floor + recovery + reimbursement,
        max_recovery=recovery,
        max_external_reimbursement=reimbursement,
        signer_bound=True,
        member_ownership_bound=True,
        automatic_forfeiture=True,
        offset_cap_certified=True,
        code_hash_bound=True,
        valid_from=NOW - 100,
        valid_until=NOW + 100,
    )


def scenario(name: str, records: list[FloorRecord]) -> dict[str, object]:
    admitted = []
    for record in records:
        value, failures = admit_floor(record)
        admitted.append(
            {
                "member": record.member,
                "reportedFloor": record.reported_floor,
                "admittedFloor": value,
                "failures": failures,
            }
        )
    certificate, ordered = threshold_certificate(records)
    return {
        "name": name,
        "admittedRecords": admitted,
        "orderedAdmittedFloors": ordered,
        "thresholdCertificate": certificate,
    }


def build_scenarios() -> list[dict[str, object]]:
    signed_only = [
        FloorRecord(member=i, reported_floor=10**12, signer_bound=True)
        for i in range(7)
    ]
    owner_funded = [
        FloorRecord(
            member=i,
            reported_floor=10**12,
            locked_member_collateral=10**6,
            signer_bound=True,
            automatic_forfeiture=True,
            offset_cap_certified=True,
            code_hash_bound=True,
            valid_from=NOW - 100,
            valid_until=NOW + 100,
        )
        for i in range(7)
    ]
    four_backed = [complete_record(i, floor) for i, floor in enumerate((5, 4, 3, 2))]
    four_backed.extend(
        FloorRecord(member=i, reported_floor=10**12, signer_bound=True)
        for i in range(4, 7)
    )
    inflated = [
        FloorRecord(**{**asdict(record), "reported_floor": 10**15})
        for record in four_backed
    ]
    revoked = deepcopy(four_backed)
    revoked[0] = FloorRecord(**{**asdict(revoked[0]), "revoked": True})
    expired = deepcopy(four_backed)
    expired[1] = FloorRecord(**{**asdict(expired[1]), "valid_until": NOW - 1})
    unknown_offset = deepcopy(four_backed)
    unknown_offset[2] = FloorRecord(
        **{**asdict(unknown_offset[2]), "offset_cap_certified": False}
    )
    return [
        scenario("signed_only_inflated", signed_only),
        scenario("owner_funded_without_member_pass_through", owner_funded),
        scenario("four_complete_member_bound_records", four_backed),
        scenario("inflated_reports_same_backing", inflated),
        scenario("one_record_revoked", revoked),
        scenario("one_record_expired", expired),
        scenario("one_offset_cap_unknown", unknown_offset),
    ]


def randomized_checks(trials: int = 10_000, seed: int = 20260802) -> dict[str, object]:
    rng = random.Random(seed)
    sound = 0
    inflation_invariant = 0
    revocation_safe = 0
    for member in range(trials):
        locked = rng.randrange(0, 10_001)
        recovery = rng.randrange(0, locked + 1)
        reimbursement = rng.randrange(0, locked - recovery + 1)
        complete = rng.choice((True, False))
        record = FloorRecord(
            member=member,
            reported_floor=rng.randrange(0, 10**12),
            locked_member_collateral=locked,
            max_recovery=recovery,
            max_external_reimbursement=reimbursement,
            signer_bound=complete,
            member_ownership_bound=complete,
            automatic_forfeiture=complete,
            offset_cap_certified=complete,
            code_hash_bound=complete,
            valid_from=NOW - 1,
            valid_until=NOW + 1,
        )
        admitted, _ = admit_floor(record)
        true_net_loss = max(0, locked - recovery - reimbursement) if complete else 0
        if admitted <= true_net_loss:
            sound += 1
        inflated = FloorRecord(**{**asdict(record), "reported_floor": 10**18})
        if admit_floor(inflated)[0] == admitted:
            inflation_invariant += 1
        revoked = FloorRecord(**{**asdict(record), "revoked": True})
        if admit_floor(revoked)[0] == 0:
            revocation_safe += 1
    return {
        "seed": seed,
        "trials": trials,
        "soundTrials": sound,
        "inflationInvariantTrials": inflation_invariant,
        "revocationSafeTrials": revocation_safe,
    }


def disclosure_frontier_check() -> dict[str, object]:
    checked = 0
    mismatches = 0
    by_positive_count: dict[str, set[int]] = {}
    for mask in range(1 << 7):
        records = []
        positive = 0
        for member in range(7):
            if mask & (1 << member):
                records.append(complete_record(member, 1))
                positive += 1
            else:
                records.append(FloorRecord(member=member, reported_floor=10**12))
        certificate, _ = threshold_certificate(records)
        expected_positive = positive > 7 - THRESHOLD
        if (certificate > 0) != expected_positive:
            mismatches += 1
        by_positive_count.setdefault(str(positive), set()).add(certificate)
        checked += 1
    return {
        "assignmentsChecked": checked,
        "mismatches": mismatches,
        "positiveExactlyWhen": "k > n - q",
        "certificateValuesByPositiveCount": {
            key: sorted(values) for key, values in sorted(by_positive_count.items())
        },
    }


def build_result() -> dict[str, object]:
    return {
        "schema": "fc-floor-admission-experiment-v1",
        "claimBoundary": {
            "reportedReservationPrice": "IGNORED_NOT_EVIDENCE",
            "admittedFloor": "max(0, lockedMemberCollateral - maxRecovery - maxExternalReimbursement)",
            "missingEvidence": "0_PUBLIC_FLOOR_CERTIFICATE",
            "unknownEconomicCost": "UNKNOWN_NOT_MEASURED",
        },
        "scenarios": build_scenarios(),
        "randomizedChecks": randomized_checks(),
        "disclosureFrontier": disclosure_frontier_check(),
    }


def main() -> None:
    result = build_result()
    scenarios = {item["name"]: item for item in result["scenarios"]}
    expected = {
        "signed_only_inflated": 0,
        "owner_funded_without_member_pass_through": 0,
        "four_complete_member_bound_records": 2,
        "inflated_reports_same_backing": 2,
        "one_record_revoked": 0,
        "one_record_expired": 0,
        "one_offset_cap_unknown": 0,
    }
    if any(
        scenarios[name]["thresholdCertificate"] != value
        for name, value in expected.items()
    ):
        raise SystemExit("floor admission scenario mismatch")
    checks = result["randomizedChecks"]
    if not all(
        checks[name] == checks["trials"]
        for name in (
            "soundTrials",
            "inflationInvariantTrials",
            "revocationSafeTrials",
        )
    ):
        raise SystemExit("floor admission randomized check failed")
    if result["disclosureFrontier"]["mismatches"] != 0:
        raise SystemExit("disclosure frontier check failed")
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("floor_admission_schema=fc-floor-admission-experiment-v1")
    for name in (
        "signed_only_inflated",
        "owner_funded_without_member_pass_through",
        "four_complete_member_bound_records",
        "inflated_reports_same_backing",
        "one_record_revoked",
        "one_record_expired",
        "one_offset_cap_unknown",
    ):
        print(f"{name}={scenarios[name]['thresholdCertificate']}")
    checks = result["randomizedChecks"]
    print(f"randomized_sound={checks['soundTrials']}/{checks['trials']}")
    print(
        f"inflation_invariant={checks['inflationInvariantTrials']}/{checks['trials']}"
    )
    print(f"revocation_safe={checks['revocationSafeTrials']}/{checks['trials']}")
    frontier = result["disclosureFrontier"]
    print(
        f"disclosure_frontier={frontier['assignmentsChecked'] - frontier['mismatches']}/"
        f"{frontier['assignmentsChecked']}"
    )
    print("floor_admission_experiment=PASS")


if __name__ == "__main__":
    main()
