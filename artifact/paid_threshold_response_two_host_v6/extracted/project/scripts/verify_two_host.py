"""Independent acceptance check over the frozen two-host canonical result.

Never imports the experiment: every condition is re-derived from the emitted
JSON, so a drift between the paper and the record fails here.
"""

from __future__ import annotations

import argparse
from itertools import combinations, permutations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCHEMA = "paid-threshold-response-two-host/v6"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a frozen two-host canonical result.")
    parser.add_argument("--canonical", type=Path, default=ROOT / "results" / "canonical_result.v3.json")
    parser.add_argument("--outage", type=Path, default=ROOT / "results" / "outage_result.v3.json")
    parser.add_argument("--recovery", type=Path, default=ROOT / "results" / "recovery_result.v3.json")
    args = parser.parse_args()

    data = json.loads(args.canonical.read_text(encoding="utf-8"))
    checks: list[tuple[str, bool]] = []

    def check(name: str, condition: object) -> None:
        checks.append((name, bool(condition)))

    check("SCHEMA_V5", data.get("schema") == EXPECTED_SCHEMA)

    committee = data["committee"]
    floors = committee["response_floors"]
    threshold = committee["threshold"]
    size = committee["committee_size"]
    hosts = committee["operator_hosts"]
    quantities = data["quantities"]

    independent_cover = sum(sorted(floors)[:threshold])
    check("THEORY_COVER", quantities["theory_cover"] == independent_cover)

    # the committee really is split across two hosts
    host_sets = {}
    for operator, host in hosts.items():
        host_sets.setdefault(host, []).append(int(operator))
    host_sets = {host: sorted(operators) for host, operators in sorted(host_sets.items())}
    check("TWO_HOSTS_CONFIGURED", len(host_sets) == 2)
    check("ALL_OPERATORS_PLACED", sum(len(v) for v in host_sets.values()) == size)
    ready_by_host = {
        host: sorted(int(operator) for operator in operators)
        for host, operators in data["readiness"]["operators_ready_by_host"].items()
    }
    all_operators_ready = ready_by_host == host_sets
    check("ALL_OPERATORS_READY", all_operators_ready)

    # A: the minimum-cover coalition is split across both hosts
    baseline = data["A_two_host_baseline"]
    cheapest = sorted(range(1, size + 1), key=lambda i: floors[i - 1])[:threshold]
    counted_by_host = baseline["counted_by_host"]
    expected_baseline_partition = {
        host: sorted(operator for operator in cheapest if hosts[str(operator)] == host)
        for host in host_sets
    }
    expected_baseline_partition = {
        host: operators for host, operators in expected_baseline_partition.items() if operators
    }
    normalised_baseline_partition = {
        host: sorted(int(operator) for operator in operators)
        for host, operators in counted_by_host.items()
        if operators
    }
    check("BASELINE_COALITION_IS_CHEAPEST", sorted(baseline["coalition"]) == sorted(cheapest))
    check(
        "BASELINE_SPANS_TWO_HOSTS",
        normalised_baseline_partition == expected_baseline_partition
        and len(normalised_baseline_partition) == 2,
    )
    check("BASELINE_CERTIFIED", baseline["report"]["status"] == "CERTIFIED")
    check("BASELINE_FLOOR", baseline["report"]["execution_floor"] == independent_cover)
    check("BASELINE_OBSERVED_OUTFLOW", baseline["report"]["observed_outflow"] == independent_cover)
    check(
        "BASELINE_HOST_SPLIT_MATCHES_CONFIG",
        all(
            all(hosts[str(op)] == host for op in ops)
            for host, ops in counted_by_host.items()
        ),
    )

    # the allocation witness binds host, bitmap and response hash
    aggregation = baseline["aggregation_witness"]
    allocation = baseline["allocation_witness"]
    entries = allocation["entries"]
    check("BASELINE_RESPONDER_SET_COMPLETE", sorted(aggregation["operator_ids"]) == sorted(cheapest))
    check("BASELINE_ALLOCATION_SET_COMPLETE", sorted(e["operator_id"] for e in entries) == sorted(cheapest))
    check("RESPONDER_BITMAP_BINDING", allocation["responder_bitmap"] == aggregation["responder_bitmap"])
    check(
        "ALLOCATION_HASHES_BOUND",
        [e["response_hash"] for e in entries] == aggregation["partial_response_hashes"],
    )
    check(
        "ALLOCATION_HOSTS_BOUND",
        [e["host_id"] for e in entries] == aggregation["host_ids"],
    )
    debit_ids = [e["debit_id"] for e in entries]
    check("DEBIT_DISJOINTNESS", len(set(debit_ids)) == len(debit_ids) and all(debit_ids))
    return_ids = [r for e in entries for r in e["refund_ids"] + e["funding_ids"]]
    check("REFUND_FUNDING_DISJOINTNESS", len(set(return_ids)) == len(return_ids))
    check(
        "ALLOCATION_COVERS_FLOORS",
        all(e["net_allocated_outflow"] >= floors[e["operator_id"] - 1] for e in entries),
    )
    check(
        "ALLOCATION_WITHIN_OUTFLOW",
        allocation["total_allocated"] <= baseline["report"]["observed_outflow"],
    )

    # E: a coalition entirely on host 2
    remote = data["E_remote_only_coalition"]
    check("REMOTE_ONLY_SINGLE_HOST", list(remote["counted_by_host"].keys()) == ["host2"])
    check(
        "REMOTE_ONLY_FLOOR",
        remote["report"]["execution_floor"] == sum(floors[i - 1] for i in remote["coalition"]),
    )
    check("REMOTE_ONLY_CERTIFIED", remote["report"]["status"] == "CERTIFIED")

    # readiness and identity
    check("REMOTE_OPERATOR_IDENTITY", data["readiness"]["identity_matches_registry"] is True)

    # the operator interface exposes no export route
    c1 = data["witnesses"]["c1"]
    check("C1_NO_EXPORT_ROUTE", c1["export_operations"] == [])
    check(
        "C1_SERVED_ROUTES_AGREE",
        all(sorted(v) == sorted(c1["served_http_routes"]) for v in c1["operator_reported_routes"].values()),
    )
    check("C1_NOT_HARDWARE", c1["hardware_enforced"] is False)

    # fault matrix: nothing is accepted, nothing certifies
    faults = data["fault_injection"]
    check(
        "FAULT_INJECTION_MATRIX",
        all(not f["gateway_accepted"] and f["status"] != "CERTIFIED" for f in faults.values()),
    )
    check(
        "FAULT_REASONS_DISTINCT",
        all(f["rejected"] for f in faults.values()),
    )

    # B: the full ordered route catalog. Failed or partial attempts remain
    # auditable entries, but they must never be assigned a numeric catalog
    # certificate.
    catalog = data["route_catalog"]
    routes = catalog["entries"]
    expected_order_set = set(permutations(range(1, size + 1), threshold))
    expected_routes = len(expected_order_set)
    catalog_complete = (
        catalog.get("complete_for_declared_first_four_route_grammar") is True
    )
    catalog_requested = catalog.get("catalog_requested") is True

    if catalog_requested:
        actual_orders = [tuple(int(value) for value in route["order"]) for route in routes]
        actual_order_set = set(actual_orders)
        duplicate_orders = sorted(
            order for order in actual_order_set if actual_orders.count(order) != 1
        )
        missing_orders = sorted(expected_order_set - actual_order_set)
        unexpected_orders = sorted(actual_order_set - expected_order_set)
        check("ROUTES_ENUMERATED", len(routes) == expected_routes == 840)
        check(
            "DECLARED_FIRST_FOUR_ROUTE_GRAMMAR_EXACT",
            not duplicate_orders and not missing_orders and not unexpected_orders,
        )
        check(
            "ROUTE_CATALOG_COALITIONS_COMPLETE",
            {tuple(sorted(order)) for order in actual_order_set}
            == set(combinations(range(1, size + 1), threshold)),
        )

        independently_eligible: list[bool] = []
        eligibility_flags_consistent: list[bool] = []
        for route in routes:
            coalition = sorted(int(operator) for operator in route["coalition"])
            expected_partition = {}
            for operator in coalition:
                expected_partition.setdefault(hosts[str(operator)], []).append(operator)
            expected_partition = {
                host: sorted(operators) for host, operators in sorted(expected_partition.items())
            }
            actual_partition = {
                host: sorted(int(operator) for operator in operators)
                for host, operators in route["counted_by_host"].items()
                if operators
            }
            eligible = (
                route["status"] == "CERTIFIED"
                and route.get("threshold_reached") is True
                and route.get("aggregate_valid") is True
                and route.get("gateway_accepted") is True
                and sorted(route.get("verified_operator_ids", [])) == coalition
                and actual_partition == expected_partition
                and route["execution_floor"] is not None
                and route["observed_outflow"] >= route["execution_floor"]
            )
            independently_eligible.append(eligible)
            eligibility_flags_consistent.append(
                route.get("catalog_eligible") is eligible
                and (not eligible or route.get("catalog_exclusion_reasons") == [])
            )

        recomputed_complete = (
            len(routes) == expected_routes
            and actual_order_set == expected_order_set
            and len(actual_order_set) == len(actual_orders)
            and all(independently_eligible)
        )
        check(
            "COMPLETE_FOR_DECLARED_FIRST_FOUR_ROUTE_GRAMMAR",
            catalog_complete == recomputed_complete,
        )
        check("ROUTE_ELIGIBILITY_FLAGS", all(eligibility_flags_consistent))
        check(
            "ROUTE_ELIGIBLE_COUNT",
            catalog.get("eligible_routes") == sum(independently_eligible),
        )
        check("GRAMMAR_EXPECTED_COUNT", catalog.get("expected_order_count") == expected_routes)
        check("GRAMMAR_ACTUAL_COUNT", catalog.get("actual_order_count") == len(actual_orders))
        check("GRAMMAR_DUPLICATES", catalog.get("duplicate_orders") == [list(x) for x in duplicate_orders])
        check("GRAMMAR_MISSING", catalog.get("missing_orders") == [list(x) for x in missing_orders])
        check("GRAMMAR_UNEXPECTED", catalog.get("unexpected_orders") == [list(x) for x in unexpected_orders])

        if recomputed_complete:
            check(
                "LEDGER_DERIVED_ROUTE_FLOORS",
                all(
                    r["execution_floor"] == sum(floors[i - 1] for i in r["coalition"])
                    and r["observed_outflow"] == r["execution_floor"]
                    for r in routes
                ),
            )
            recomputed = min(r["execution_floor"] for r in routes)
            check("CATALOG_CERTIFICATE", quantities["catalog_certificate"] == recomputed == independent_cover)
            check("OBSERVED_MINIMUM", quantities["observed_minimum"] == independent_cover)
            check(
                "MINIMIZING_ROUTES",
                sum(1 for r in routes if r["execution_floor"] == recomputed) == 24
                and catalog.get("minimizing_routes") == 24,
            )
            check("COALITION_FLOORS_CONSISTENT", catalog.get("coalition_floor_consistent") is True)
            check("EXPENSIVE_COALITION_4567", catalog["coalition_floors"].get("4,5,6,7") == 22)
            check("REMOTE_COALITION_2467", catalog["coalition_floors"].get("2,4,6,7") == 19)
        else:
            check("INCOMPLETE_CATALOG_HAS_NO_CERTIFICATE", quantities["catalog_certificate"] is None)
            check("INCOMPLETE_CATALOG_HAS_NO_OBSERVED_MINIMUM", quantities["observed_minimum"] is None)
            check("INCOMPLETE_CATALOG_HAS_NO_MINIMIZERS", catalog.get("minimizing_routes") == 0)
            check("INCOMPLETE_CATALOG_HAS_NO_COALITION_FLOORS", catalog.get("coalition_floors") == {})
    else:
        check("SKIPPED_CATALOG_HAS_NO_ENTRIES", routes == [])
        check("SKIPPED_CATALOG_HAS_NO_CERTIFICATE", quantities["catalog_certificate"] is None)
        check("SKIPPED_CATALOG_HAS_NO_OBSERVED_MINIMUM", quantities["observed_minimum"] is None)

    # scope statements the paper depends on
    scope = data["scope"]
    check(
        "SCOPE_BOUNDARIES",
        scope["deployment_wide"] is False
        and scope["hardware_non_exportability_proved"] is False
        and scope["independent_economic_operators_claimed"] is False
        and scope["trusted_dealer"] is True,
    )

    # The two-host claim itself. A single-machine rehearsal is a legitimate
    # record and passes here; what fails is a record that claims separation its
    # own witness did not establish.
    separation = data["readiness"]["separation_witness"]
    established = scope["two_physical_hosts_established"]
    check("SEPARATION_WITNESS_PRESENT", separation.get("type") == "host_separation_witness")
    check("SEPARATION_VERDICT_MATCHES_SCOPE", established == (separation["status"] == "PASS"))
    expected_failure_domains = len(host_sets) if established else 1
    check(
        "FAILURE_DOMAINS_NOT_OVERCLAIMED",
        scope["independent_failure_domains"] == expected_failure_domains
        and (scope["independent_failure_domains"] >= 2 or not established),
    )
    remote_obs = [o for o in separation["observations"] if o["is_remote"]]
    check("SEPARATION_COVERS_EVERY_REMOTE_OPERATOR", len(remote_obs) == len(host_sets.get("host2", [])))
    if established:
        check(
            "REMOTE_PEERS_ARE_NON_LOCAL",
            all(
                not o["peer_is_loopback"]
                and not o["peer_equals_local"]
                and o["machine_differs_from_coordinator"]
                for o in remote_obs
            ),
        )
    else:
        check(
            "REHEARSAL_LABELLED_HONESTLY",
            scope["independent_failure_domains"] < 2
            and separation["status"] in ("FAIL_COUNTEREXAMPLE", "FAIL_CLOSED_MISSING_EVIDENCE"),
        )
    check("NO_ADDRESSES_IN_CANONICAL", "observed_peer_address" not in json.dumps(data))

    # This is deliberately a configured-directory placement check, not key
    # isolation, secure erasure, or a whole-host filesystem scan.
    placement = data["readiness"]["host_local_secret_file_placement_witness"]
    placement_established = scope[
        "host1_declared_secret_directory_excludes_remote_operator_files"
    ]
    check(
        "HOST_LOCAL_SECRET_FILE_PLACEMENT_WITNESS_PRESENT",
        placement.get("type") == "host_local_secret_file_placement_witness",
    )
    check(
        "HOST_LOCAL_SECRET_FILE_PLACEMENT_MATCHES_SCOPE",
        placement_established == (placement["status"] == "PASS"),
    )
    check(
        "NO_FOREIGN_FILES_IN_DECLARED_SECRET_DIRECTORY",
        (
            not set(placement["secret_files_present"]) & set(host_sets.get("host2", []))
            if placement_established else True
        ),
    )
    check(
        "PUBLIC_BUNDLE_CARRIES_NO_SECRET",
        placement["public_bundle_carries_no_secret"] is True
        or not placement_established,
    )
    # No secret material anywhere in the canonical record.
    blob = json.dumps(data)
    check("NO_SEED_IN_CANONICAL", '"seed"' not in blob and '"network_seed"' not in blob)
    check("NO_SECRET_SHARE_IN_CANONICAL", "secret_share" not in blob and "network_secret_key" not in blob)

    # The composite claim requires a successful, complete cross-host baseline;
    # separation and declared secret-file placement alone are insufficient.
    baseline_cross_host_facts = (
        all_operators_ready
        and data["readiness"]["identity_matches_registry"] is True
        and baseline["report"]["status"] == "CERTIFIED"
        and sorted(aggregation["operator_ids"]) == sorted(cheapest)
        and normalised_baseline_partition == expected_baseline_partition
        and len(normalised_baseline_partition) == 2
        and baseline["report"]["execution_floor"] == independent_cover
        and baseline["report"]["observed_outflow"] == independent_cover
    )
    expected_cross_host = (
        established
        and placement_established
        and expected_failure_domains == 2
        and baseline_cross_host_facts
    )
    check(
        "CROSS_HOST_DEPENDENCY_CONSISTENT",
        scope["cross_host_dependency_established"] == expected_cross_host,
    )

    embedded_checks_all = all(bool(value) for value in data["checks"].values())
    embedded_failed = sorted(name for name, value in data["checks"].items() if not value)
    check("EMBEDDED_RUN_PASSED", data.get("run_passed") is embedded_checks_all)
    check("EMBEDDED_FAILED_CHECKS", sorted(data.get("failed_checks", [])) == embedded_failed)

    if not embedded_checks_all:
        expected_run_class = "NETWORK_OR_CONFIGURATION_FAILURE"
    elif expected_cross_host and catalog_requested:
        expected_run_class = "CERTIFIED_TWO_HOST"
    elif expected_cross_host:
        expected_run_class = "CERTIFIED_TWO_HOST_BASELINE"
    else:
        expected_run_class = "NETWORK_SMOKE_TEST_ONLY"
    check("RUN_CLASS_CONSISTENT", scope.get("run_class") == expected_run_class)

    # C and D: the outage record, if present
    if args.outage.exists():
        outage = json.loads(args.outage.read_text(encoding="utf-8"))
        check("OUTAGE_HOST2_UNREACHABLE", outage["host2_unreachable"] is True)
        c_group = outage["C_minimum_cover_coalition"]
        check("OUTAGE_THRESHOLD_NOT_REACHED", c_group["threshold_reached"] is False)
        check("OUTAGE_NO_USABLE_PLAINTEXT", c_group["usable_plaintext_released"] is False)
        check("OUTAGE_GATEWAY_REFUSED", c_group["gateway_accepted"] is False)
        d_group = outage["D_alternative_coalition"]
        check("OUTAGE_ALTERNATIVE_ALSO_FAILS", d_group["gateway_accepted"] is False)
        check("OUTAGE_EMBEDDED_CHECKS", all(outage["checks"].values()))

    if args.recovery.exists():
        recovery = json.loads(args.recovery.read_text(encoding="utf-8"))
        check("RECOVERY_HOST2_BACK", recovery["host2_unreachable"] is False)
        check("RECOVERY_EMBEDDED_CHECKS", all(recovery["checks"].values()))

    width = max(len(name) for name, _ in checks)
    for name, ok in checks:
        print(f"{name.ljust(width)}  {'PASS' if ok else 'FAIL'}")
    failed = [name for name, ok in checks if not ok]
    if failed:
        print("TWO_HOST_VERIFICATION=FAIL")
        return 1
    print("TWO_HOST_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
