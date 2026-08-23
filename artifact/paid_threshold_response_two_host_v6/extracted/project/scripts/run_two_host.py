"""Host 1 entry point for the two-host threshold-response experiment.

Runs experiment groups A--E and the fault-injection matrix, then writes a
canonical result (topology-independent in its acceptance fields) and a run metadata
file (addresses, ports, PIDs, latencies).
"""

from __future__ import annotations

import argparse
from itertools import combinations, permutations
from pathlib import Path
import platform
import secrets
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.certificate import brute_force_weighted, catalog_certificate, theory_cover, weighted_dp  # noqa: E402
from ptr_v3.coordinator import Coordinator, OperatorEndpoint  # noqa: E402
from ptr_v3.evidence import CERTIFIED, REFUTED, UNKNOWN  # noqa: E402
from ptr_v3.experiment import SCHEMA, Committee, assess, c1_witness, run_order  # noqa: E402
from ptr_v3.network_identity import OperatorRegistry  # noqa: E402
from ptr_v3.operator_server import MACHINE_DIGEST, RUNTIME_SOURCE_DIGEST  # noqa: E402
from ptr_v3.utils import file_sha256, read_json, write_json  # noqa: E402
from ptr_v3.witness import build_host_local_secret_file_placement_witness, build_separation_witness  # noqa: E402


def build_coordinator(committee: Committee, topology: dict[str, Any], ports: dict[int, int], timeout: float):
    # Everything here is derived from the public committee bundle. The coordinator
    # holds no seed and no secret share; it recognises public keys, it cannot mint
    # them.
    registry = OperatorRegistry.from_public(committee.operator_hosts, committee.network_public_keys)
    endpoints = {}
    for operator_id, host_id in committee.operator_hosts.items():
        address = topology[host_id]["address"]
        endpoints[operator_id] = OperatorEndpoint(operator_id, host_id, address, ports[operator_id])
    return registry, Coordinator(
        registry,
        endpoints,
        committee.public_share_list(),
        expected_runtime_source_digest=RUNTIME_SOURCE_DIGEST,
        timeout_s=timeout,
    )


def _partition_by_host(coalition: list[int] | tuple[int, ...], operator_hosts: dict[int, str] | Any) -> dict[str, list[int]]:
    """Return the exact configured host partition of a responder coalition."""

    partition: dict[str, list[int]] = {}
    for operator_id in coalition:
        partition.setdefault(str(operator_hosts[operator_id]), []).append(int(operator_id))
    return {host: sorted(operators) for host, operators in sorted(partition.items())}


def _normalise_partition(value: dict[str, Any]) -> dict[str, list[int]]:
    return {
        str(host): sorted(int(operator_id) for operator_id in operators)
        for host, operators in sorted(value.items())
        if operators
    }


def _ordered_route_count(size: int, threshold: int) -> int:
    result = 1
    for offset in range(threshold):
        result *= size - offset
    return result


def _route_eligibility(outcome: Any, aggregation: Any, report: Any, coalition: tuple[int, ...], committee: Committee) -> tuple[bool, list[str]]:
    """Decide whether one attempted route may enter the numeric catalog.

    A failed or partial attempt remains in the audit trail, but it is never a
    numeric route floor. This predicate deliberately does not compare the floor
    with the theoretical cover; that comparison is a later experiment check.
    """

    expected_ids = sorted(int(operator_id) for operator_id in coalition)
    verified_ids = sorted(int(response.operator_id) for response in outcome.verified)
    aggregated_ids = sorted(int(operator_id) for operator_id in aggregation.operator_ids)
    expected_partition = _partition_by_host(expected_ids, committee.operator_hosts)
    actual_partition = _normalise_partition(aggregation.counted_by_host())

    reasons: list[str] = []
    if len(expected_ids) != committee.threshold:
        reasons.append("declared coalition is not threshold-sized")
    if report.status != CERTIFIED:
        reasons.append(f"evidence report status is {report.status}")
    if not outcome.threshold_reached:
        reasons.append("threshold was not reached")
    if not outcome.aggregate_valid:
        reasons.append("threshold aggregate is invalid")
    if not outcome.gateway_accepted:
        reasons.append("gateway did not release the scoped usable capability")
    if verified_ids != expected_ids:
        reasons.append("verified responder set differs from the declared coalition")
    if aggregated_ids != expected_ids:
        reasons.append("aggregation witness differs from the declared coalition")
    if actual_partition != expected_partition:
        reasons.append("counted host partition differs from the configured coalition partition")
    if report.execution_floor is None:
        reasons.append("no ledger-derived execution floor")
    if report.execution_floor is not None and report.observed_outflow < report.execution_floor:
        reasons.append("observed outflow is below the claimed execution floor")

    return not reasons, reasons


def _summarise_catalog(
    routes: list[dict[str, Any]],
    expected_orders: set[tuple[int, ...]],
) -> dict[str, Any]:
    """Price only an exact enumeration of the declared first-four grammar.

    The grammar is every length-four sequence of distinct committee identifiers;
    execution stops after those first four responders. Completeness is equality of
    route tuples, not a self-reported flag and not merely a matching row count.
    """

    incomplete = [route for route in routes if not route["catalog_eligible"]]
    actual_orders = [tuple(int(value) for value in route["order"]) for route in routes]
    actual_set = set(actual_orders)
    duplicate_orders = sorted(
        order for order in actual_set if actual_orders.count(order) != 1
    )
    missing_orders = sorted(expected_orders - actual_set)
    unexpected_orders = sorted(actual_set - expected_orders)
    complete = (
        not incomplete
        and not duplicate_orders
        and not missing_orders
        and not unexpected_orders
        and len(actual_orders) == len(expected_orders)
    )
    common = {
        "complete_for_declared_first_four_route_grammar": complete,
        "eligible_count": len(routes) - len(incomplete),
        "expected_order_count": len(expected_orders),
        "actual_order_count": len(actual_orders),
        "duplicate_orders": [list(order) for order in duplicate_orders],
        "missing_orders": [list(order) for order in missing_orders],
        "unexpected_orders": [list(order) for order in unexpected_orders],
        "incomplete_route_ids": [route["route_id"] for route in incomplete],
    }
    if not complete:
        return {
            **common,
            "catalog_certificate": None,
            "observed_minimum": None,
            "minimizing_route_ids": [],
            "coalition_floors": {},
            "coalition_floor_consistent": False,
        }

    catalog_value = catalog_certificate(route["execution_floor"] for route in routes)
    observed_minimum = min(int(route["observed_outflow"]) for route in routes)
    minimizing = [
        route["route_id"] for route in routes
        if route["execution_floor"] == catalog_value
    ]
    values_by_coalition: dict[tuple[int, ...], set[int]] = {}
    for route in routes:
        coalition = tuple(int(operator_id) for operator_id in route["coalition"])
        values_by_coalition.setdefault(coalition, set()).add(
            int(route["execution_floor"])
        )
    consistent = all(len(values) == 1 for values in values_by_coalition.values())
    coalition_floors = {
        ",".join(map(str, coalition)): next(iter(values))
        for coalition, values in sorted(values_by_coalition.items())
        if len(values) == 1
    }
    return {
        **common,
        "catalog_certificate": catalog_value,
        "observed_minimum": observed_minimum,
        "minimizing_route_ids": minimizing,
        "coalition_floors": coalition_floors,
        "coalition_floor_consistent": consistent,
    }


def _classify_run(
    checks: dict[str, bool],
    *,
    cross_host_required: bool,
    catalog_requested: bool,
) -> tuple[list[str], str]:
    """Return failed checks and an honest run classification."""

    failed = sorted(key for key, value in checks.items() if not value)
    if failed:
        return failed, "NETWORK_OR_CONFIGURATION_FAILURE"
    if cross_host_required and catalog_requested:
        return failed, "CERTIFIED_TWO_HOST"
    if cross_host_required:
        return failed, "CERTIFIED_TWO_HOST_BASELINE"
    return failed, "NETWORK_SMOKE_TEST_ONLY"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the two-host paid threshold response experiment.")
    parser.add_argument("--committee", type=Path, default=ROOT / "config" / "committee.public.v3.json")
    parser.add_argument("--topology", type=Path, default=ROOT / "config" / "topology.v3.json")
    parser.add_argument("--host1", type=Path, default=ROOT / "config" / "host1.v3.json")
    parser.add_argument("--host2", type=Path, default=ROOT / "config" / "host2.v3.json")
    parser.add_argument("--canonical", type=Path, default=ROOT / "results" / "canonical_result.v3.json")
    parser.add_argument("--metadata", type=Path, default=ROOT / "results" / "run_metadata.v3.json")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--skip-routes", action="store_true", help="skip the 840-route enumeration")
    parser.add_argument(
        "--run-id",
        default=None,
        help="prefix for every order id; a fresh value keeps persistent replay logs from rejecting a re-run. "
        "Defaults to random.",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    # Order ids are salted with a per-invocation run id so that operators' on-disk
    # replay logs never reject a legitimate re-run: the deterministic nonce is a
    # function of the order id, so a fresh run id yields fresh nonces. The salt
    # lives in the ciphertext derivation too, so it never has to be reused.
    run_id = args.run_id or secrets.token_hex(4)

    def oid(name: str) -> str:
        return f"{run_id}-{name}"

    committee = Committee.from_file(args.committee)
    topology = read_json(args.topology)
    h1, h2 = read_json(args.host1), read_json(args.host2)
    ports = {int(k): int(v) for k, v in {**h1["ports"], **h2["ports"]}.items()}
    registry, coordinator = build_coordinator(committee, topology, ports, args.timeout)
    floors = list(committee.response_floors)

    # --- readiness -------------------------------------------------------
    health: dict[int, Any] = {}
    for operator_id in sorted(committee.operator_hosts):
        info = coordinator.health(operator_id)
        if info is not None:
            health[operator_id] = info
    ready_by_host = {
        host: sorted(i for i in committee.operators_on(host) if i in health) for host in committee.hosts()
    }
    expected_ready_by_host = {host: committee.operators_on(host) for host in committee.hosts()}
    all_operators_ready = ready_by_host == expected_ready_by_host
    identity_ok = all_operators_ready and all(
        health[i]["host_id"] == committee.operator_hosts[i]
        and int(health[i]["network_public_key"], 16) == registry.public_key(i)
        for i in health
    )
    runtime_source_ok = all_operators_ready and all(
        health[i].get("runtime_source_digest") == RUNTIME_SOURCE_DIGEST for i in health
    )

    # --- host separation -------------------------------------------------
    # Decided from observed sockets and reported fingerprints, never from the
    # committee file's host labels. A loopback rehearsal must say so here.
    probes = [
        probe
        for probe in (coordinator.probe_endpoint(i) for i in sorted(committee.operator_hosts))
        if probe is not None
    ]
    separation = build_separation_witness(
        local_host_id=h1["self_host_id"],
        local_machine_digest=MACHINE_DIGEST,
        probes=probes,
        health_by_operator=health,
        operator_hosts=dict(committee.operator_hosts),
    )

    # --- declared secret-file placement ---------------------------------
    # Checks only the declared host-local secret directory and public bundle.
    # It does not scan the whole host or prove erasure/non-exportability.
    secret_placement = build_host_local_secret_file_placement_witness(
        local_host_id=h1["self_host_id"],
        secret_dir=ROOT / "secrets" / h1["self_host_id"],
        public_bundle_path=args.committee,
        operator_hosts=dict(committee.operator_hosts),
    )

    cover = theory_cover(committee.response_floors, committee.threshold)
    cheapest = [i + 1 for i, _ in sorted(enumerate(floors), key=lambda kv: kv[1])[: committee.threshold]]

    results: dict[str, Any] = {}

    # --- A. two-host baseline over the minimum-cover coalition -----------
    outcome, payloads = run_order(coordinator, committee, order_id=oid("A-baseline"), coalition=cheapest)
    agg, alloc, cov, report = assess(outcome, committee)
    results["A_two_host_baseline"] = {
        "coalition": cheapest,
        "counted_by_host": agg.counted_by_host(),
        "aggregation_witness": agg.to_dict(),
        "allocation_witness": alloc.to_dict(),
        "report": report.to_dict(),
    }
    baseline_payloads = payloads
    expected_baseline_partition = _partition_by_host(cheapest, committee.operator_hosts)
    actual_baseline_partition = _normalise_partition(agg.counted_by_host())
    baseline_verified_ids = sorted(response.operator_id for response in outcome.verified)
    baseline_complete = (
        report.status == CERTIFIED
        and outcome.threshold_reached
        and outcome.aggregate_valid
        and outcome.gateway_accepted
        and baseline_verified_ids == sorted(cheapest)
        and sorted(agg.operator_ids) == sorted(cheapest)
    )

    # --- E. remote-only coalition ---------------------------------------
    remote_only = committee.operators_on("host2")[: committee.threshold]
    outcome_e, _ = run_order(coordinator, committee, order_id=oid("E-remote-only"), coalition=remote_only)
    agg_e, _, _, report_e = assess(outcome_e, committee)
    results["E_remote_only_coalition"] = {
        "coalition": remote_only,
        "counted_by_host": agg_e.counted_by_host(),
        "report": report_e.to_dict(),
    }

    # --- expensive coalition --------------------------------------------
    expensive = sorted(range(1, committee.committee_size + 1), key=lambda i: floors[i - 1])[-committee.threshold :]
    outcome_x, _ = run_order(coordinator, committee, order_id=oid("X-expensive"), coalition=sorted(expensive))
    _, _, _, report_x = assess(outcome_x, committee)

    # --- fault injection --------------------------------------------------
    faults: dict[str, Any] = {}
    fault_specs = [
        ("tamper_partial", {"tamper": "partial"}),
        ("tamper_proof", {"tamper": "proof"}),
        ("tamper_buyer", {"tamper": "buyer"}),
        ("tamper_order_id", {"tamper": "order"}),
        ("stale_epoch", {"tamper": "epoch"}),
        ("operator_impersonation", {"tamper": "impersonate"}),
    ]
    for index, (name, kwargs) in enumerate(fault_specs):
        out, _ = run_order(
            coordinator,
            committee,
            order_id=oid(f"F{index}-{name}"),
            coalition=cheapest,
            tamper_operator=cheapest[0],
            **kwargs,
        )
        _, _, _, rep = assess(out, committee)
        faults[name] = {
            "rejected": [r.to_dict() for r in out.rejected],
            "threshold_reached": out.threshold_reached,
            "gateway_accepted": out.gateway_accepted,
            "status": rep.status,
        }
    replayed, _ = run_order(
        coordinator,
        committee,
        order_id=oid("F6-replay"),
        coalition=cheapest,
        replay_from={i: baseline_payloads[i] for i in cheapest if i in baseline_payloads},
    )
    _, _, _, replay_report = assess(replayed, committee)
    faults["replayed_response"] = {
        "rejected": [r.to_dict() for r in replayed.rejected],
        "threshold_reached": replayed.threshold_reached,
        "gateway_accepted": replayed.gateway_accepted,
        "status": replay_report.status,
    }
    results["fault_injection"] = faults

    # --- B. every ordered threshold route ---------------------------------
    routes: list[dict[str, Any]] = []
    if not args.skip_routes:
        index = 0
        for coalition in combinations(range(1, committee.committee_size + 1), committee.threshold):
            for order in permutations(coalition):
                out, _ = run_order(
                    coordinator,
                    committee,
                    order_id=oid(f"R-{index:04d}"),
                    coalition=coalition,
                    order=order,
                )
                agg_r, _, _, rep = assess(out, committee)
                eligible, exclusion_reasons = _route_eligibility(out, agg_r, rep, coalition, committee)
                routes.append(
                    {
                        "route_id": f"R-{index:04d}",
                        "coalition": list(coalition),
                        "order": list(order),
                        "counted_by_host": agg_r.counted_by_host(),
                        "execution_floor": rep.execution_floor,
                        "observed_outflow": rep.observed_outflow,
                        "status": rep.status,
                        "sum_of_member_floors": sum(floors[i - 1] for i in coalition),
                        "threshold_reached": out.threshold_reached,
                        "aggregate_valid": out.aggregate_valid,
                        "gateway_accepted": out.gateway_accepted,
                        "verified_operator_ids": sorted(response.operator_id for response in out.verified),
                        "catalog_eligible": eligible,
                        "catalog_exclusion_reasons": exclusion_reasons,
                    }
                )
                index += 1

    expected_orders = set(permutations(range(1, committee.committee_size + 1), committee.threshold))
    expected_route_count = len(expected_orders)
    catalog_requested = not args.skip_routes
    catalog_summary = _summarise_catalog(routes, expected_orders) if catalog_requested else {
        "complete_for_declared_first_four_route_grammar": False,
        "eligible_count": 0,
        "expected_order_count": expected_route_count,
        "actual_order_count": 0,
        "duplicate_orders": [],
        "missing_orders": [],
        "unexpected_orders": [],
        "incomplete_route_ids": [],
        "catalog_certificate": None,
        "observed_minimum": None,
        "minimizing_route_ids": [],
        "coalition_floors": {},
        "coalition_floor_consistent": False,
    }
    catalog_value = catalog_summary["catalog_certificate"]
    observed_minimum = catalog_summary["observed_minimum"]
    minimizing = catalog_summary["minimizing_route_ids"]

    weights = [3, 2, 2, 1, 1, 1, 1]
    wprices = [5, 2, 3, 1, 1, 4, 6]
    wbrute, wset = brute_force_weighted(weights, wprices, 6)

    physical_hosts_observed = len(committee.hosts()) if separation.passed else 1

    code_manifest_digest_path = ROOT / "config" / "code_manifest.v1.sha256"
    source_coverage_result_path = ROOT / "results" / "source_coverage_kernel.v1.json"
    if not code_manifest_digest_path.exists() or not source_coverage_result_path.exists():
        raise RuntimeError("run the code-manifest and source-coverage verifiers before the experiment")
    code_manifest_sha256 = code_manifest_digest_path.read_text(encoding="ascii").strip().upper()
    source_coverage_result = read_json(source_coverage_result_path)
    source_coverage_sha256 = file_sha256(source_coverage_result_path)
    source_obligations_pass = (
        source_coverage_result.get("status") == "PROVED_IN_RESTRICTED_SOURCE_MODEL"
        and all(item.get("status") == "PROVED_IN_RESTRICTED_SOURCE_MODEL" for item in source_coverage_result.get("obligations", {}).values())
    )

    canonical: dict[str, Any] = {
        "schema": SCHEMA,
        "source_binding": {
            "code_manifest_sha256": code_manifest_sha256,
            "source_coverage_result_sha256": source_coverage_sha256,
            "source_coverage_schema": source_coverage_result.get("schema"),
            "source_coverage_status": source_coverage_result.get("status"),
        },
        "scope": {
            "claim": "finite-language named-buyer net-outflow certificate over two configured hosts",
            "deployment_wide": False,
            "coverage_scope": "declared finite program language over the two configured hosts",
            "hardware_non_exportability_proved": False,
            "real_threshold_crypto": True,
            "trusted_dealer": True,
            # Derived from the separation witness, not from the host labels in
            # the committee file: a loopback rehearsal reports one domain.
            "independent_failure_domains": physical_hosts_observed,
            "configured_host_labels": len(committee.hosts()),
            "host_separation_status": separation.status,
            "two_physical_hosts_established": separation.passed,
            # Whether the declared Host 1 secret directory excludes remote files.
            "host_local_secret_file_placement_status": secret_placement.status,
            "host1_declared_secret_directory_excludes_remote_operator_files": secret_placement.passed,
            # The deployment-consistency observation records both: two machines
            # and local-only placement in the declared secret directory.
            "cross_host_dependency_established": False,
            "run_class": "UNCLASSIFIED",
            "independent_economic_operators_claimed": False,
            "rng": "the dealer seed is a reproducibility fixture for key setup; each capability token and "
            "ElGamal encryption nonce comes from the operating-system CSPRNG; proof and signature nonces "
            "are deterministic functions of secret witness material and the full statement",
        },
        "committee": {
            "committee_size": committee.committee_size,
            "threshold": committee.threshold,
            "response_floors": floors,
            "buyer": committee.buyer,
            "resource": committee.resource,
            "epoch": committee.epoch,
            "operator_hosts": {str(k): v for k, v in sorted(committee.operator_hosts.items())},
        },
        "operator_registry": registry.to_dict(),
        "crypto": {
            "scheme": "Shamir threshold ElGamal over RFC3526 group14 with Chaum-Pedersen partial proofs",
            "network_identity": "Schnorr over the same group, deterministic nonces",
            "key_distribution": "trusted dealer at setup; each host runs from its own secret files and the public bundle",
            "proof_nonce": "operator-derived from its own share and the ciphertext; not supplied by the requester",
            "public_key": hex(committee.public_key),
            "public_shares": [hex(committee.public_shares[i]) for i in range(1, committee.committee_size + 1)],
        },
        "readiness": {
            "operators_ready_by_host": ready_by_host,
            "identity_matches_registry": identity_ok,
            "runtime_source_digest": RUNTIME_SOURCE_DIGEST,
            "runtime_source_matches": runtime_source_ok,
            "separation_witness": separation.to_dict(),
            "host_local_secret_file_placement_witness": secret_placement.to_dict(),
        },
        "quantities": {
            "theory_cover": cover,
            "catalog_certificate": catalog_value,
            "observed_minimum": observed_minimum,
            "baseline_execution_floor": report.execution_floor,
            "remote_only_execution_floor": report_e.execution_floor,
            "expensive_execution_floor": report_x.execution_floor,
        },
        "route_catalog": {
            "catalog_requested": catalog_requested,
            "complete_for_declared_first_four_route_grammar": catalog_summary["complete_for_declared_first_four_route_grammar"] if catalog_requested else None,
            "routes_enumerated": len(routes),
            "eligible_routes": catalog_summary["eligible_count"] if catalog_requested else None,
            "declared_route_grammar": "ordered first four distinct responders; stop after the fourth response",
            "expected_order_count": catalog_summary["expected_order_count"] if catalog_requested else None,
            "actual_order_count": catalog_summary["actual_order_count"] if catalog_requested else None,
            "duplicate_orders": catalog_summary["duplicate_orders"] if catalog_requested else [],
            "missing_orders": catalog_summary["missing_orders"] if catalog_requested else [],
            "unexpected_orders": catalog_summary["unexpected_orders"] if catalog_requested else [],
            "incomplete_route_ids": catalog_summary["incomplete_route_ids"] if catalog_requested else [],
            "all_floors_ledger_derived": (
                catalog_summary["complete_for_declared_first_four_route_grammar"]
                and all(r["execution_floor"] is not None for r in routes)
            ) if catalog_requested else None,
            "catalog_certificate": catalog_value,
            "minimizing_routes": len(minimizing),
            "coalition_floor_consistent": catalog_summary["coalition_floor_consistent"] if catalog_requested else None,
            "coalition_floors": catalog_summary["coalition_floors"],
            "entries": routes,
        },
        "witnesses": {"c1": c1_witness(committee, ROOT / "src", health)},
        "weighted_committee": {
            "weights": weights,
            "prices": wprices,
            "threshold": 6,
            "brute_force_certificate": wbrute,
            "brute_force_coalition": list(wset),
            "dynamic_program_certificate": weighted_dp(weights, wprices, 6),
        },
        **results,
    }

    host2_ops = committee.operators_on("host2")
    checks = {
        "all_operators_ready": all_operators_ready,
        "remote_operator_identity": identity_ok,
        "runtime_source_digest_matches": runtime_source_ok,
        "baseline_certified": report.status == CERTIFIED,
        "baseline_complete": baseline_complete,
        "baseline_spans_two_hosts": actual_baseline_partition == expected_baseline_partition
        and len(actual_baseline_partition) == 2,
        "baseline_floor_is_ledger_derived": report.execution_floor == cover,
        "baseline_observed_outflow_matches_floor": report.observed_outflow == cover,
        "remote_only_coalition_certified": report_e.status == CERTIFIED,
        "remote_only_is_single_host": list(agg_e.counted_by_host().keys()) == ["host2"],
        "remote_only_floor": report_e.execution_floor == sum(floors[i - 1] for i in remote_only),
        "expensive_floor_not_cover": report_x.execution_floor == sum(floors[i - 1] for i in expensive),
        "fault_matrix": all(
            not entry["gateway_accepted"] and entry["status"] != CERTIFIED for entry in faults.values()
        ),
        "weighted_dp_matches_bruteforce": wbrute == weighted_dp(weights, wprices, 6),
        "source_coverage_kernel_passed": source_obligations_pass,
        "source_binding_complete": (
            len(code_manifest_sha256) == 64
            and len(source_coverage_sha256) == 64
            and source_coverage_result.get("schema") == "ptr-restricted-source-kernel/v2"
        ),
        # The run may legitimately be a single-machine rehearsal; what it may
        # not do is claim separation the witness did not establish.
        "scope_does_not_overclaim_separation": (
            canonical["scope"]["two_physical_hosts_established"] is separation.passed
            and canonical["scope"]["independent_failure_domains"]
            == (len(committee.hosts()) if separation.passed else 1)
            and (canonical["scope"]["independent_failure_domains"] >= 2 or not separation.passed)
        ),
        "scope_matches_secret_file_placement": (
            canonical["scope"]["host1_declared_secret_directory_excludes_remote_operator_files"] is secret_placement.passed
        ),
    }
    if catalog_requested:
        checks.update(
            {
                "routes_enumerated_840": len(routes) == expected_route_count == 840,
                "complete_for_declared_first_four_route_grammar": bool(catalog_summary["complete_for_declared_first_four_route_grammar"]),
                "every_route_catalog_eligible": all(r["catalog_eligible"] for r in routes),
                "ledger_derived_route_floors": bool(catalog_summary["complete_for_declared_first_four_route_grammar"])
                and all(r["execution_floor"] is not None for r in routes),
                "catalog_certificate_matches_theory": catalog_value == cover,
                "observed_minimum_matches_theory": observed_minimum == cover,
                "no_cover_substitution": all(
                    r["catalog_eligible"]
                    and r["execution_floor"] == r["sum_of_member_floors"]
                    for r in routes
                ),
                "coalition_floor_consistent": bool(catalog_summary["coalition_floor_consistent"]),
                "minimizing_routes_24": len(minimizing) == 24,
            }
        )
    cross_host_required = (
        separation.passed
        and secret_placement.passed
        and checks["all_operators_ready"]
        and checks["remote_operator_identity"]
        and checks["baseline_certified"]
        and checks["baseline_complete"]
        and checks["baseline_spans_two_hosts"]
        and checks["baseline_floor_is_ledger_derived"]
        and checks["baseline_observed_outflow_matches_floor"]
        and physical_hosts_observed == 2
    )
    failed, run_class = _classify_run(
        checks,
        cross_host_required=cross_host_required,
        catalog_requested=catalog_requested,
    )

    canonical["scope"]["cross_host_dependency_established"] = cross_host_required
    canonical["scope"]["run_class"] = run_class
    canonical["checks"] = checks
    canonical["failed_checks"] = failed
    canonical["run_passed"] = not failed
    write_json(args.canonical, canonical)

    all_latencies = [x for r in [outcome, outcome_e, outcome_x] for x in r.latencies_ms]
    metadata = {
        "schema": "paid-threshold-response-two-host-metadata/v6",
        "canonical_schema": SCHEMA,
        "run_id": run_id,
        "platform": platform.platform(),
        "python_version": sys.version,
        "topology": topology,
        "ports": {str(k): v for k, v in sorted(ports.items())},
        "host_separation": separation.to_metadata_dict(),
        "host_local_secret_files_present": secret_placement.secret_files_present,
        "response_latency_ms": {
            "count": len(all_latencies),
            "min": min(all_latencies) if all_latencies else None,
            "max": max(all_latencies) if all_latencies else None,
            "mean": (sum(all_latencies) / len(all_latencies)) if all_latencies else None,
        },
        "elapsed_ms": (time.perf_counter() - started) * 1000,
    }
    write_json(args.metadata, metadata)

    print(f"CANONICAL_RESULT={args.canonical}")
    for host in committee.hosts():
        print(f"{host.upper()}_OPERATORS_READY={len(ready_by_host[host])}")
    print(f"REMOTE_OPERATOR_IDENTITY={'PASS' if identity_ok else 'FAIL'}")
    print(f"HOST_SEPARATION={separation.status}")
    print(f"DISTINCT_MACHINES_OBSERVED={physical_hosts_observed}")
    if not separation.passed:
        print(f"SEPARATION_NOT_ESTABLISHED={separation.reason}")
    print(f"HOST_LOCAL_SECRET_FILE_PLACEMENT={secret_placement.status}")
    if not secret_placement.passed:
        print(f"HOST_LOCAL_SECRET_FILE_PLACEMENT_NOT_ESTABLISHED={secret_placement.reason}")
    print("HOST1_COUNTED_RESPONDERS=" + ",".join(map(str, agg.counted_by_host().get("host1", []))))
    print("HOST2_COUNTED_RESPONDERS=" + ",".join(map(str, agg.counted_by_host().get("host2", []))))
    print(f"THEORY_COVER={cover}")
    print(f"BASELINE_EXECUTION_FLOOR={report.execution_floor}")
    print(f"BASELINE_STATUS={report.status}")
    print(f"REMOTE_COALITION_{''.join(map(str, remote_only))}={report_e.execution_floor}")
    print(f"EXPENSIVE_COALITION_{''.join(map(str, sorted(expensive)))}={report_x.execution_floor}")
    if catalog_requested:
        print(f"ROUTES_ENUMERATED={len(routes)}")
        print(f"COMPLETE_FOR_DECLARED_FIRST_FOUR_ROUTE_GRAMMAR={str(bool(catalog_summary['complete_for_declared_first_four_route_grammar'])).lower()}")
        print(f"CATALOG_CERTIFICATE={catalog_value if catalog_value is not None else 'NOT_CERTIFIED'}")
        print(f"OBSERVED_MINIMUM={observed_minimum if observed_minimum is not None else 'NOT_CERTIFIED'}")
        print(f"MINIMIZING_ROUTES={len(minimizing)}")
    print(f"FAULT_INJECTION_MATRIX={'PASS' if checks['fault_matrix'] else 'FAIL'}")
    print(f"CROSS_HOST_DEPENDENCY_ESTABLISHED={str(cross_host_required).lower()}")
    print(f"RUN_CLASS={run_class}")
    if failed:
        print("FAILED_CHECKS=" + ",".join(sorted(failed)))
        return 1
    if catalog_requested:
        print("TWO_HOST_V6=PASS")
    else:
        print("TWO_HOST_BASELINE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
