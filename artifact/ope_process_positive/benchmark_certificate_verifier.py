#!/usr/bin/env python3
"""Measure certificate size and independent-verifier scaling.

Route prefixes are timing probes only. They are never reported as complete
certificates; the full 35-route run remains the certification check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
from typing import Any

from verify_process_certificate import CERTIFICATE_PATH, SCHEMA_PATH, verify_certificate


HERE = Path(__file__).resolve().parent
RESULT_PATH = HERE / "results" / "verifier_benchmark.v1.json"
ROUTE_COUNTS = (1, 5, 10, 20, 35)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def measure(repeats: int) -> dict[str, Any]:
    certificate = json.loads(CERTIFICATE_PATH.read_text(encoding="utf-8"))
    preflight = verify_certificate(CERTIFICATE_PATH, verify_eip191=True)
    points: list[dict[str, Any]] = []
    for count in ROUTE_COUNTS:
        samples = [
            float(
                verify_certificate(
                    CERTIFICATE_PATH,
                    route_limit=count,
                    verify_eip191=False,
                )["elapsed_ms"]
            )
            for _ in range(repeats)
        ]
        points.append(
            {
                "cryptographically_checked_routes": count,
                "route_payload_bytes": sum(canonical_size(route) for route in certificate["routes"][:count]),
                "minimum_ms": min(samples),
                "median_ms": statistics.median(samples),
                "maximum_ms": max(samples),
                "samples_ms": samples,
                "certification_status": "FULL_CERTIFICATE" if count == 35 else "SCALING_PROBE_ONLY",
            }
        )
    return {
        "schema": "ope-process-independent-verifier-benchmark/v1",
        "claim_type": "authenticated-relative-process-cost",
        "certificate": {
            "path": "artifact/ope_process_positive/results/ope_process_positive.v2.json",
            "sha256": file_sha256(CERTIFICATE_PATH),
            "bytes": CERTIFICATE_PATH.stat().st_size,
            "declared_routes": len(certificate["routes"]),
            "operator_responses": sum(len(route["operator_responses"]) for route in certificate["routes"]),
        },
        "schema_document": {
            "path": "artifact/ope_process_positive/schema/ope_process_certificate.schema.json",
            "sha256": file_sha256(SCHEMA_PATH),
            "bytes": SCHEMA_PATH.stat().st_size,
        },
        "preflight": {
            "schema_input_eip191_and_full_crypto": "PASS",
            "verified_routes": int(preflight["cryptographically_verified_routes"]),
            "operator_signatures": int(preflight["operator_signatures_verified"]),
            "chaum_pedersen_proofs": int(preflight["chaum_pedersen_proofs_verified"]),
        },
        "method": {
            "repeats_per_point": repeats,
            "eip191_preflight_runs": 1,
            "timed_points_exclude_node_eip191_startup": True,
            "route_prefixes_are_not_certificates": True,
            "timer": "time.perf_counter",
        },
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "operating_system": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor() or "not-reported-by-platform",
            "logical_cpu_count": os.cpu_count(),
        },
        "scaling": points,
        "limitations": [
            "timings are machine-specific wall-clock measurements",
            "prefix runs measure verifier growth and do not discharge route completeness",
            "the certificate excludes gas, host compromise, side channels, and undeclared external transfers",
        ],
    }


def validate_committed(committed: dict[str, Any], current: dict[str, Any]) -> None:
    if committed["schema"] != "ope-process-independent-verifier-benchmark/v1":
        raise ValueError("benchmark schema mismatch")
    if committed["certificate"]["sha256"] != current["certificate"]["sha256"]:
        raise ValueError("benchmark is bound to a different certificate")
    if committed["certificate"]["bytes"] != current["certificate"]["bytes"]:
        raise ValueError("certificate-size measurement is stale")
    if committed["schema_document"]["sha256"] != current["schema_document"]["sha256"]:
        raise ValueError("benchmark is bound to a different JSON Schema")
    if [item["cryptographically_checked_routes"] for item in committed["scaling"]] != list(ROUTE_COUNTS):
        raise ValueError("benchmark route scale is incomplete")
    if [item["route_payload_bytes"] for item in committed["scaling"]] != [
        item["route_payload_bytes"] for item in current["scaling"]
    ]:
        raise ValueError("benchmark route-size measurements are stale")
    if committed["preflight"] != current["preflight"]:
        raise ValueError("benchmark preflight counts are stale")
    if not all(
        item["minimum_ms"] > 0
        and item["minimum_ms"] <= item["median_ms"] <= item["maximum_ms"]
        for item in committed["scaling"]
    ):
        raise ValueError("committed benchmark timing samples are invalid")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    current = measure(args.repeats)
    if args.write:
        write_json(RESULT_PATH, current)
    else:
        if not RESULT_PATH.is_file():
            raise FileNotFoundError("committed verifier benchmark missing")
        validate_committed(json.loads(RESULT_PATH.read_text(encoding="utf-8")), current)
    full = current["scaling"][-1]
    print(f"OPE_CERTIFICATE_BYTES={current['certificate']['bytes']}")
    print(f"OPE_FULL_VERIFY_MEDIAN_MS={full['median_ms']:.3f}")
    print(f"OPE_VERIFIER_SCALING_POINTS={len(current['scaling'])}")
    print("OPE_VERIFIER_BENCHMARK=PASS")


if __name__ == "__main__":
    main()
