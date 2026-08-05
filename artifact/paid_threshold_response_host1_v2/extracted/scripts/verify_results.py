"""Independent acceptance check over a frozen canonical result.

This script never imports the experiment: it re-derives every acceptance
condition from the emitted JSON, so a drift between the paper's numbers and the
recorded run fails here rather than in review.
"""

from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SCHEMA = "paid-threshold-response-host1/v2"


def fail(checks: list[tuple[str, bool]], name: str, condition: bool) -> None:
    checks.append((name, bool(condition)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a frozen canonical result.")
    parser.add_argument("--canonical", type=Path, default=ROOT / "results" / "canonical_result.v2.json")
    args = parser.parse_args()
    data = json.loads(args.canonical.resolve().read_text(encoding="utf-8"))

    checks: list[tuple[str, bool]] = []
    fail(checks, "SCHEMA_V2", data.get("schema") == EXPECTED_SCHEMA)

    floors = data["config"]["response_floors"]
    threshold = data["config"]["threshold"]
    committee = data["config"]["committee_size"]
    quantities = data["quantities"]
    catalog = data["route_catalog"]
    routes = catalog["entries"]

    # 1. the closed form, recomputed here from the declared floors alone
    independent_cover = sum(sorted(floors)[:threshold])
    fail(checks, "THEORY_COVER", quantities["theory_cover"] == independent_cover)

    # 2. every route floor equals the sum of its coalition's member floors
    per_route_ok = True
    for entry in routes:
        expected = sum(floors[i - 1] for i in entry["coalition"])
        if entry["execution_floor"] != expected or entry["observed_outflow"] != expected:
            per_route_ok = False
            break
    fail(checks, "LEDGER_DERIVED_ROUTE_FLOORS", per_route_ok)

    # 3. the catalog is the full ordered enumeration
    expected_routes = 1
    for k in range(threshold):
        expected_routes = expected_routes * (committee - k)
    expected_routes = expected_routes  # C(n,q) * q! == n!/(n-q)!
    fail(checks, "ROUTES_ENUMERATED", len(routes) == expected_routes == 840)
    seen = {(tuple(entry["coalition"]), tuple(entry["order"])) for entry in routes}
    fail(checks, "ROUTE_CATALOG_DISTINCT", len(seen) == len(routes))
    fail(
        checks,
        "ROUTE_CATALOG_COMPLETE",
        {c for c, _ in seen} == set(combinations(range(1, committee + 1), threshold)),
    )

    # 4. the catalog certificate is the minimum of ledger-derived floors
    recomputed = min(entry["execution_floor"] for entry in routes)
    fail(checks, "CATALOG_CERTIFICATE", quantities["catalog_certificate"] == recomputed == independent_cover)
    fail(checks, "OBSERVED_MINIMUM", quantities["observed_minimum"] == independent_cover)
    fail(
        checks,
        "MINIMIZING_ROUTES",
        sum(1 for entry in routes if entry["execution_floor"] == recomputed) == 24,
    )

    # 5. an expensive coalition must not report the cover value
    dearest = catalog["coalition_floors"].get("4,5,6,7")
    fail(checks, "EXPENSIVE_COALITION_FLOOR_22", dearest == 22)
    fail(
        checks,
        "NO_COVER_SUBSTITUTION",
        all(entry["execution_floor"] == sum(floors[i - 1] for i in entry["coalition"]) for entry in routes),
    )

    # 6. C2 allocation witness
    aggregation = data["witnesses"]["c2_baseline_aggregation"]
    allocation = data["witnesses"]["c2_baseline_allocation"]
    entries = allocation["entries"]
    fail(checks, "AGGREGATION_BITMAP_BINDING", allocation["responder_bitmap"] == aggregation["responder_bitmap"])
    fail(
        checks,
        "ALLOCATION_HASHES_BOUND",
        [entry["response_hash"] for entry in entries] == aggregation["partial_response_hashes"],
    )
    debit_ids = [entry["debit_id"] for entry in entries]
    fail(checks, "DEBIT_DISJOINTNESS", len(set(debit_ids)) == len(debit_ids) and all(debit_ids))
    return_ids = [rid for entry in entries for rid in entry["refund_ids"] + entry["funding_ids"]]
    fail(checks, "REFUND_FUNDING_DISJOINTNESS", len(set(return_ids)) == len(return_ids))
    fail(
        checks,
        "ALLOCATION_COVERS_FLOORS",
        all(entry["net_allocated_outflow"] >= floors[entry["operator_id"] - 1] for entry in entries),
    )
    fail(
        checks,
        "ALLOCATION_WITHIN_OUTFLOW",
        allocation["total_allocated"] <= data["baseline"]["report"]["observed_outflow"],
    )
    fail(checks, "C2_ALLOCATION_WITNESS", data["witnesses"]["c2_baseline_check"]["ok"])

    # 7. C1 and C3 witnesses
    c1 = data["witnesses"]["c1"]
    fail(
        checks,
        "C1_WITNESS",
        c1["export_operations"] == []
        and c1["hardware_enforced"] is False
        and bool(c1["source_hashes"]),
    )
    c3 = data["witnesses"]["c3"]
    fail(
        checks,
        "C3_MINIMUM_COVER_WITNESS",
        c3["ledger_derived_floor"] == independent_cover and c3["gap"] == 0 and c3["attained"] is True,
    )

    # 8. ablation matrix: exactly one FAIL_COUNTEREXAMPLE, on the target gate
    matrix_ok = True
    off_diagonal_failures = 0
    for name, entry in data["ablations"].items():
        target = entry["target_gate"]
        for gate, verdict in entry["report"]["gates"].items():
            if gate == target:
                if verdict["status"] != "FAIL_COUNTEREXAMPLE":
                    matrix_ok = False
            else:
                if verdict["status"] not in ("PASS", "NOT_APPLICABLE"):
                    matrix_ok = False
                    off_diagonal_failures += 1
        if entry["report"]["status"] != "REFUTED":
            matrix_ok = False
    fail(checks, "ABLATION_MATRIX", matrix_ok and off_diagonal_failures == 0)

    # 9. UNKNOWN and REFUTED are not conflated
    cases = data["verdict_cases"]
    fail(
        checks,
        "UNKNOWN_VS_COUNTEREXAMPLE",
        cases["missing_coverage_evidence"]["report"]["status"] == "UNKNOWN"
        and cases["missing_coverage_evidence"]["report"]["gates"]["B5"]["status"]
        == "FAIL_CLOSED_MISSING_EVIDENCE"
        and cases["missing_ordering_evidence"]["report"]["status"] == "UNKNOWN"
        and cases["missing_ordering_evidence"]["report"]["gates"]["B3"]["status"]
        == "FAIL_CLOSED_MISSING_EVIDENCE"
        and cases["explicit_bypass_trace"]["report"]["status"] == "REFUTED"
        and cases["explicit_bypass_trace"]["report"]["gates"]["B5"]["status"] == "FAIL_COUNTEREXAMPLE",
    )

    # 10. adoption threshold and weighted complexity
    fail(
        checks,
        "ADOPTION_THRESHOLD",
        all(
            entry["positive"] == (entry["positive_members"] > committee - threshold)
            and entry["cover_value"] == sum(sorted(entry["prices"])[:threshold])
            for entry in data["adoption_threshold"]
        ),
    )
    weighted = data["weighted_committee"]
    fail(checks, "WEIGHTED_DP", weighted["brute_force_certificate"] == weighted["dynamic_program_certificate"])

    # 11. scope statements the paper depends on
    scope = data["scope"]
    fail(
        checks,
        "SCOPE_BOUNDARIES",
        scope["deployment_wide"] is False
        and scope["hardware_non_exportability_proved"] is False
        and scope["physical_hosts"] == 1
        and scope["trusted_dealer"] is True,
    )

    fail(checks, "EMBEDDED_CHECKS", all(data["checks"].values()))

    width = max(len(name) for name, _ in checks)
    for name, ok in checks:
        print(f"{name.ljust(width)}  {'PASS' if ok else 'FAIL'}")
    failed = [name for name, ok in checks if not ok]
    if failed:
        print("RESULT_VERIFICATION=FAIL")
        return 1
    print("RESULT_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
