"""Emit the sealed-composition coverage certificate (Theorem 5 instantiation).

Builds the two-host service manifest, verifies the baseline is SEALED, then
applies one mutation per condition (LC0--LC7) plus a cached-output bypass and
records that each is caught as COVERAGE_NOT_ESTABLISHED naming exactly the
violated condition. Writes ``coverage_certificate.v3.json``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.contracts import COVERAGE_NOT_ESTABLISHED, SEALED, verify_composition  # noqa: E402
from ptr_v3.service_model import MUTATIONS, baseline_manifest  # noqa: E402
from ptr_v3.utils import write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit the coverage certificate.")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "coverage_certificate.v3.json")
    args = parser.parse_args()

    base = baseline_manifest()
    baseline = verify_composition(base)

    mutations: dict[str, dict[str, object]] = {}
    for name, (fn, expected_lc) in MUTATIONS.items():
        report = verify_composition(fn(base))
        conditions = sorted({v["condition"] for v in report.violations})
        mutations[name] = {
            "status": report.status,
            "expected_condition": expected_lc,
            "violated_conditions": conditions,
            "isolates_expected_condition": conditions == [expected_lc],
            "counter_derivation": report.counter_derivation,
        }

    result = {
        "schema": "paid-threshold-response-two-host-coverage/v5",
        "manifest": base.to_dict(),
        "baseline": baseline.to_dict(),
        "mutations": mutations,
        "checks": {
            "baseline_sealed": baseline.status == SEALED,
            "every_mutation_caught": all(m["status"] == COVERAGE_NOT_ESTABLISHED for m in mutations.values()),
            "each_isolates_one_condition": all(m["isolates_expected_condition"] for m in mutations.values()),
            "bypass_has_counter_derivation": mutations["cached_output_bypass"]["counter_derivation"] is not None,
            "all_conditions_covered": {v[1] for v in MUTATIONS.values()} == {"LC0", "LC1", "LC2", "LC3", "LC4", "LC5", "LC6", "LC7"},
        },
    }
    write_json(args.output, result)

    print(f"COVERAGE_CERTIFICATE={args.output}")
    print(f"BASELINE={baseline.status}")
    for name, m in mutations.items():
        print(f"MUTATION {name} -> {m['status']} ({','.join(m['violated_conditions'])})")
    failed = [k for k, v in result["checks"].items() if not v]
    if failed:
        print("FAILED_CHECKS=" + ",".join(sorted(failed)))
        return 1
    print("COVERAGE_CERTIFICATE_RUN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
