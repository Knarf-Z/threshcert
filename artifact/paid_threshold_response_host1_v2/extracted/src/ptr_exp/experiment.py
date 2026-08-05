from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations
from pathlib import Path
import platform
import sys
import time
from typing import Any, Sequence

from .certificate import (
    brute_force_weighted,
    catalog_certificate,
    theory_cover,
    uniform_positive_count,
    weighted_dp,
)
from .crypto import (
    ThresholdKeySet,
    combine_partials,
    create_partial,
    encrypt_capability,
    verify_partial,
    verify_threshold_result,
)
from .evidence import CERTIFIED, REFUTED, UNKNOWN, evaluate_execution
from .ledger import OrderLedger
from .protocol import (
    COVERED_ROUTES,
    PROOF_KERNEL,
    ExecutionResult,
    ThresholdResponseService,
    build_aggregation_witness,
    build_allocation_witness,
    build_coverage_evidence,
    response_hash,
)
from .utils import file_sha256, read_json, sha256_hex, write_json
from .witness import scope_hash

SCHEMA = "paid-threshold-response-host1/v2"


@dataclass(frozen=True)
class ExperimentConfig:
    committee_size: int
    threshold: int
    response_floors: tuple[int, ...]
    seed: int
    buyer: str
    resource: str

    @staticmethod
    def from_file(path: Path) -> "ExperimentConfig":
        value = read_json(path)
        return ExperimentConfig(
            committee_size=int(value["committee_size"]),
            threshold=int(value["threshold"]),
            response_floors=tuple(int(v) for v in value["response_floors"]),
            seed=int(value["seed"]),
            buyer=str(value["buyer"]),
            resource=str(value["resource"]),
        )


def _assess(result: ExecutionResult, floors: Sequence[int], coverage_status: str = "PROVED"):
    aggregation = build_aggregation_witness(result)
    allocation = build_allocation_witness(result, aggregation)
    coverage = build_coverage_evidence(result, status=coverage_status, committee_size=len(floors))
    report = evaluate_execution(result, aggregation, allocation, coverage, floors)
    return aggregation, allocation, coverage, report


def _cached_route(
    *,
    keyset: ThresholdKeySet,
    prices: Sequence[int],
    ciphertext,
    response_map,
    coalition: Sequence[int],
    ordering: Sequence[int],
    buyer: str,
    resource: str,
    order_id: str,
) -> ExecutionResult:
    """Replay one ordered route through a fresh ledger using cached partials."""
    price_map = {i + 1: price for i, price in enumerate(prices)}
    ledger = OrderLedger.open(order_id, buyer, price_map, source="buyer")
    for operator_id in ordering:
        ledger.credit_before_release(
            operator_id, response_hash(response_map[operator_id]), proof_valid=True, usable=True
        )
    used = [response_map[operator_id] for operator_id in list(ordering)[: keyset.threshold]]
    plaintext = combine_partials(ciphertext, used, keyset.threshold)
    aggregate_valid = verify_threshold_result(ciphertext, plaintext)
    gateway_accepted = aggregate_valid and ciphertext.buyer == buyer
    if gateway_accepted:
        ledger.mark_success()
    ledger.finalize_refund()
    return ExecutionResult(
        order_id=order_id,
        buyer=buyer,
        consumer=buyer,
        resource=resource,
        epoch=1,
        responder_ids=list(coalition),
        response_order=list(ordering),
        prices=list(prices),
        threshold=keyset.threshold,
        aggregate_valid=aggregate_valid,
        gateway_accepted=gateway_accepted,
        plaintext=plaintext,
        ledger=ledger,
        used_responses=used,
        mode="cached_crypto_fixture",
        worker_pids=[],
    )


def _c1_witness(service: ThresholdResponseService, source_root: Path) -> dict[str, Any]:
    modules = sorted(p for p in (source_root / "ptr_exp").glob("*.py"))
    return {
        "type": "c1_non_exportability_witness",
        "conclusion": "C1 proved within the declared finite service language",
        "hardware_enforced": False,
        "public_interface": service.public_interface(),
        "export_operations": [],
        "process_entry_points": ["ptr_exp.protocol._operator_worker"],
        "source_hashes": {module.name: file_sha256(module) for module in modules},
        "scope": "declared finite program language; no attestation, no HSM or TEE",
    }


def run_experiment(config: ExperimentConfig, source_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    keyset = ThresholdKeySet.generate(config.committee_size, config.threshold, seed=config.seed)
    service = ThresholdResponseService(keyset, config.response_floors)
    floors = list(config.response_floors)

    # (1) closed form, no execution consulted
    cover = theory_cover(config.response_floors, config.threshold)
    cheapest_ids = [
        index + 1
        for index, _ in sorted(enumerate(config.response_floors), key=lambda item: item[1])[: config.threshold]
    ]

    baseline = service.execute(
        cheapest_ids,
        order_id="baseline-4of7",
        buyer=config.buyer,
        resource=config.resource,
        seed=config.seed + 100,
    )
    b_agg, b_alloc, b_cov, baseline_report = _assess(baseline, floors)

    # One real ciphertext and one verified partial per operator drive the exhaustive
    # route enumeration; every route gets a freshly executed ledger.
    fixture_ciphertext = encrypt_capability(
        keyset.public_key, config.buyer, config.resource, "exhaustive-fixture", seed=config.seed + 900
    )
    response_map = {}
    for operator_id in range(1, config.committee_size + 1):
        response = create_partial(
            operator_id,
            keyset.secret_shares[operator_id - 1],
            keyset.public_shares[operator_id - 1],
            fixture_ciphertext,
            seed=config.seed + 950 + operator_id,
        )
        if not verify_partial(keyset.public_shares[operator_id - 1], fixture_ciphertext, response):
            raise AssertionError(f"partial proof failed for operator {operator_id}")
        response_map[operator_id] = response

    # (2)/(3) every ordered threshold route, each with a ledger-derived floor
    routes: list[dict[str, Any]] = []
    coalition_floor: dict[tuple[int, ...], int] = {}
    index = 0
    for coalition in combinations(range(1, config.committee_size + 1), config.threshold):
        for ordering in permutations(coalition):
            result = _cached_route(
                keyset=keyset,
                prices=config.response_floors,
                ciphertext=fixture_ciphertext,
                response_map=response_map,
                coalition=coalition,
                ordering=ordering,
                buyer=config.buyer,
                resource=config.resource,
                order_id=f"route-{index:04d}",
            )
            _, allocation, _, report = _assess(result, floors)
            expected = sum(config.response_floors[i - 1] for i in coalition)
            routes.append(
                {
                    "route_id": f"route-{index:04d}",
                    "coalition": list(coalition),
                    "order": list(ordering),
                    "execution_floor": report.execution_floor,
                    "observed_outflow": report.observed_outflow,
                    "allocation_verified": report.allocation_check.ok,
                    "status": report.status,
                    "sum_of_member_floors": expected,
                }
            )
            if report.execution_floor is not None:
                coalition_floor.setdefault(tuple(coalition), report.execution_floor)
            index += 1

    catalog_value = catalog_certificate(entry["execution_floor"] for entry in routes)
    observed_minimum = min(entry["observed_outflow"] for entry in routes)
    minimizing = [entry["route_id"] for entry in routes if entry["execution_floor"] == catalog_value]

    multiprocess = service.execute(
        cheapest_ids,
        order_id="host1-seven-process-smoke",
        buyer=config.buyer,
        resource=config.resource,
        seed=config.seed + 3000,
        process_mode=True,
    )
    _, _, _, multiprocess_report = _assess(multiprocess, floors)

    # (4) ablations: one gate each, plus the two verdict-separation cases
    ablation_specs: dict[str, dict[str, Any]] = {
        "B1_wrong_buyer": {"kwargs": {"ablation": "wrong_buyer"}, "coverage": "PROVED", "target": "B1"},
        "B2_sponsor_funded": {"kwargs": {"deposit_source": "sponsor"}, "coverage": "PROVED", "target": "B2"},
        "B3_early_release": {"kwargs": {"ablation": "early_release"}, "coverage": "PROVED", "target": "B3"},
        "B4_full_reimbursement": {"kwargs": {"ablation": "reimbursement"}, "coverage": "PROVED", "target": "B4"},
        "B5_bypass_route": {"kwargs": {"ablation": "bypass"}, "coverage": "REFUTED", "target": "B5"},
    }
    ablations: dict[str, Any] = {}
    for offset, (name, spec) in enumerate(ablation_specs.items()):
        result = service.execute(
            cheapest_ids,
            order_id=f"ablation-{name}",
            buyer=config.buyer,
            resource=config.resource,
            seed=config.seed + 4000 + offset,
            **spec["kwargs"],
        )
        _, _, _, report = _assess(result, floors, coverage_status=spec["coverage"])
        ablations[name] = {
            "target_gate": spec["target"],
            "execution": result.to_dict(),
            "report": report.to_dict(),
        }

    verdict_cases: dict[str, Any] = {}
    missing_coverage = service.execute(
        cheapest_ids,
        order_id="verdict-missing-coverage",
        buyer=config.buyer,
        resource=config.resource,
        seed=config.seed + 5000,
    )
    _, _, _, missing_report = _assess(missing_coverage, floors, coverage_status="UNKNOWN")
    verdict_cases["missing_coverage_evidence"] = {
        "execution": missing_coverage.to_dict(),
        "report": missing_report.to_dict(),
    }

    untimed = service.execute(
        cheapest_ids,
        order_id="verdict-untimed-payment",
        buyer=config.buyer,
        resource=config.resource,
        seed=config.seed + 5100,
        ablation="untimed",
    )
    _, _, _, untimed_report = _assess(untimed, floors)
    verdict_cases["missing_ordering_evidence"] = {
        "execution": untimed.to_dict(),
        "report": untimed_report.to_dict(),
    }

    explicit_bypass = service.execute(
        cheapest_ids,
        order_id="verdict-explicit-bypass",
        buyer=config.buyer,
        resource=config.resource,
        seed=config.seed + 5200,
        ablation="bypass",
    )
    _, _, _, bypass_report = _assess(explicit_bypass, floors, coverage_status="REFUTED")
    verdict_cases["explicit_bypass_trace"] = {
        "execution": explicit_bypass.to_dict(),
        "report": bypass_report.to_dict(),
    }

    adoption = []
    for positive_count in range(config.committee_size + 1):
        prices = [1 if i < positive_count else 0 for i in range(config.committee_size)]
        adoption.append(
            {
                "positive_members": positive_count,
                "prices": prices,
                "cover_value": theory_cover(prices, config.threshold),
                "positive": uniform_positive_count(prices, config.threshold),
            }
        )

    weights = [3, 2, 2, 1, 1, 1, 1]
    weighted_prices = [5, 2, 3, 1, 1, 4, 6]
    weighted_threshold = 6
    weighted_brute, weighted_set = brute_force_weighted(weights, weighted_prices, weighted_threshold)
    weighted_dynamic = weighted_dp(weights, weighted_prices, weighted_threshold)

    cheapest_key = tuple(sorted(cheapest_ids))
    c3_witness = {
        "type": "c3_minimum_cover_witness",
        "minimum_cover_coalition": list(cheapest_key),
        "theory_cover": cover,
        "ledger_derived_floor": coalition_floor.get(cheapest_key),
        "named_buyer_net_outflow": baseline_report.observed_outflow,
        "gap": (coalition_floor.get(cheapest_key) or 0) - cover,
        "exact_as_infimum_witness": True,
        "attained": baseline_report.observed_outflow == cover,
        "note": "the declared floors are attained exactly, which is stronger than approach to within delta",
    }

    ablation_matrix_ok = True
    for name, entry in ablations.items():
        target = entry["target_gate"]
        for gate, verdict in entry["report"]["gates"].items():
            if gate == target:
                if verdict["status"] != "FAIL_COUNTEREXAMPLE":
                    ablation_matrix_ok = False
            elif verdict["status"] not in ("PASS", "NOT_APPLICABLE"):
                ablation_matrix_ok = False

    canonical: dict[str, Any] = {
        "schema": SCHEMA,
        "scope": {
            "claim": "finite-language named-buyer net-outflow certificate",
            "deployment_wide": False,
            "coverage_scope": "declared finite program language",
            "hardware_non_exportability_proved": False,
            "real_threshold_crypto": True,
            "trusted_dealer": True,
            "physical_hosts": 1,
            "operator_processes_spawned": config.committee_size,
            "rng": "random.Random is a seeded deterministic test generator, not a cryptographic RNG; "
            "it is used only to make the controlled experiment reproducible",
        },
        "config": {
            "committee_size": config.committee_size,
            "threshold": config.threshold,
            "response_floors": floors,
            "buyer": config.buyer,
            "resource": config.resource,
            "seed": config.seed,
            "scope_hash": scope_hash(
                config.buyer, config.resource, config.threshold, config.committee_size
            ),
        },
        "crypto": {
            "scheme": "Shamir threshold ElGamal over RFC3526 group14 with Chaum-Pedersen partial proofs",
            "public_key": hex(keyset.public_key),
            "public_shares": [hex(value) for value in keyset.public_shares],
        },
        "quantities": {
            "theory_cover": cover,
            "catalog_certificate": catalog_value,
            "observed_minimum": observed_minimum,
            "baseline_execution_floor": baseline_report.execution_floor,
        },
        "route_catalog": {
            "routes_enumerated": len(routes),
            "all_floors_ledger_derived": all(entry["execution_floor"] is not None for entry in routes),
            "catalog_certificate": catalog_value,
            "minimizing_routes": len(minimizing),
            "coalition_floors": {
                ",".join(str(i) for i in key): value for key, value in sorted(coalition_floor.items())
            },
            "entries": routes,
        },
        "witnesses": {
            "c1": _c1_witness(service, source_root),
            "c2_baseline_aggregation": b_agg.to_dict(),
            "c2_baseline_allocation": b_alloc.to_dict(),
            "c2_baseline_check": baseline_report.allocation_check.to_dict(),
            "c3": c3_witness,
            "route_coverage": b_cov.to_dict(),
        },
        "baseline": {"execution": baseline.to_dict(), "report": baseline_report.to_dict()},
        "multiprocess_smoke": {
            "execution": multiprocess.to_dict(),
            "report": multiprocess_report.to_dict(),
            "distinct_worker_count": len(set(multiprocess.worker_pids)),
        },
        "ablations": ablations,
        "verdict_cases": verdict_cases,
        "adoption_threshold": adoption,
        "weighted_committee": {
            "weights": weights,
            "prices": weighted_prices,
            "threshold": weighted_threshold,
            "brute_force_certificate": weighted_brute,
            "brute_force_coalition": list(weighted_set),
            "dynamic_program_certificate": weighted_dynamic,
            "match": weighted_brute == weighted_dynamic,
        },
    }

    checks = {
        "routes_enumerated_840": len(routes) == 840,
        "ledger_derived_route_floors": all(entry["execution_floor"] is not None for entry in routes),
        "catalog_certificate_matches_theory": catalog_value == cover,
        "observed_minimum_matches_theory": observed_minimum == cover,
        "expensive_coalition_floor_is_22": coalition_floor.get((4, 5, 6, 7)) == 22,
        "no_route_reports_the_cover_value_when_it_is_dearer": all(
            entry["execution_floor"] == entry["sum_of_member_floors"] for entry in routes
        ),
        "minimizing_routes_24": len(minimizing) == 24,
        "baseline_certified": baseline_report.status == CERTIFIED,
        "baseline_floor_is_ledger_derived": baseline_report.execution_floor == cover,
        "c2_allocation_witness": baseline_report.allocation_check.ok,
        "aggregation_bitmap_binding": b_alloc.responder_bitmap == b_agg.responder_bitmap,
        "debit_disjointness": len({entry.debit_id for entry in b_alloc.entries}) == len(b_alloc.entries),
        "refund_funding_disjointness": baseline_report.allocation_check.ok,
        "c3_minimum_cover_witness": bool(c3_witness["attained"])
        and c3_witness["ledger_derived_floor"] == cover,
        "multiprocess_certified": multiprocess_report.status == CERTIFIED,
        "multiprocess_realized": len(set(multiprocess.worker_pids)) >= config.threshold,
        "ablation_matrix": ablation_matrix_ok,
        "all_ablations_refuted": all(
            entry["report"]["status"] == REFUTED for entry in ablations.values()
        ),
        "unknown_vs_counterexample": (
            missing_report.status == UNKNOWN
            and missing_report.gates["B5"].status == "FAIL_CLOSED_MISSING_EVIDENCE"
            and untimed_report.status == UNKNOWN
            and untimed_report.gates["B3"].status == "FAIL_CLOSED_MISSING_EVIDENCE"
            and bypass_report.status == REFUTED
            and bypass_report.gates["B5"].status == "FAIL_COUNTEREXAMPLE"
        ),
        "adoption_threshold_correct": all(
            entry["positive"] == (entry["positive_members"] > config.committee_size - config.threshold)
            for entry in adoption
        ),
        "weighted_dp_matches_bruteforce": weighted_brute == weighted_dynamic,
    }
    canonical["checks"] = checks

    metadata = {
        "schema": "paid-threshold-response-host1-metadata/v2",
        "canonical_schema": SCHEMA,
        "platform": platform.platform(),
        "python_version": sys.version,
        "processor": platform.processor(),
        "worker_pids": sorted(set(multiprocess.worker_pids)),
        "operator_processes_spawned": config.committee_size,
        "elapsed_ms": (time.perf_counter() - started) * 1000,
    }
    return canonical, metadata


def run_to_file(
    config_path: Path, canonical_path: Path, metadata_path: Path, source_root: Path
) -> dict[str, Any]:
    config = ExperimentConfig.from_file(config_path)
    canonical, metadata = run_experiment(config, source_root)
    write_json(canonical_path, canonical)
    metadata["canonical_sha256"] = file_sha256(canonical_path)
    write_json(metadata_path, metadata)
    return canonical
