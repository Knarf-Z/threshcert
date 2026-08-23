from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fidelity_core import load_manifest, sha256_file, verify_tree  # noqa: E402
from source_coverage_kernel import analyze  # noqa: E402


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def all_true(value: dict[str, Any]) -> bool:
    return bool(value) and all(item is True for item in value.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the end-to-end finite-language payment certificate.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "end_to_end_certificate.v1.json",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    paths = {
        "source": root / "results" / "source_coverage_kernel.v1.json",
        "manifest": root / "config" / "code_manifest.v1.json",
        "manifest_digest": root / "config" / "code_manifest.v1.sha256",
        "coverage": root / "results" / "coverage_certificate.v3.json",
        "capability": root / "results" / "capability_certificate.v3.json",
        "canonical": root / "results" / "canonical_result.v3.json",
        "outage": root / "results" / "outage_result.v3.json",
        "recovery": root / "results" / "recovery_result.v3.json",
    }
    missing = sorted(name for name, path in paths.items() if not path.exists())
    if missing:
        print("END_TO_END_INPUTS_MISSING=" + ",".join(missing))
        return 2

    stored_source = load(paths["source"])
    live_source = analyze(root)
    manifest = load_manifest(paths["manifest"])
    manifest_digest = paths["manifest_digest"].read_text(encoding="ascii").strip().upper()
    live_binding = verify_tree(root, manifest, expected_manifest_digest=manifest_digest)
    coverage = load(paths["coverage"])
    capability = load(paths["capability"])
    canonical = load(paths["canonical"])
    outage = load(paths["outage"])
    recovery = load(paths["recovery"])

    obligations = stored_source.get("obligations", {})
    consequence_names = {
        "LC1_SOURCE_PRODUCER_COMPLETENESS",
        "LC3_SOURCE_SECRET_CONFINEMENT",
        "LC5_SOURCE_LIFECYCLE_CLOSURE",
        "LC7_SOURCE_DELIVERY_ROOT",
    }
    source_obligations_pass = consequence_names == set(obligations) and all(
        obligations[name].get("status") == "PROVED_IN_RESTRICTED_SOURCE_MODEL" for name in consequence_names
    )

    source_result_sha256 = sha256_file(paths["source"])
    canonical_result_sha256 = sha256_file(paths["canonical"])
    binding = canonical.get("source_binding", {})
    outage_binding = outage.get("source_binding", {})
    recovery_binding = recovery.get("source_binding", {})
    quantities = canonical.get("quantities", {})
    route_catalog = canonical.get("route_catalog", {})
    baseline = capability.get("baseline", {})

    checks = {
        "RESTRICTED_SOURCE_THEOREM_LIVE_PROVED": live_source.get("status") == "PROVED_IN_RESTRICTED_SOURCE_MODEL",
        "SOURCE_KERNEL_RESULT_MATCHES_LIVE": (
            stored_source.get("status") == "PROVED_IN_RESTRICTED_SOURCE_MODEL"
            and stored_source.get("checks") == live_source.get("checks")
            and stored_source.get("obligations") == live_source.get("obligations")
            and stored_source.get("source_sha256") == live_source.get("source_sha256")
        ),
        "CONSEQUENTIAL_LC_PROVED_IN_RESTRICTED_MODEL": source_obligations_pass,
        "CODE_MANIFEST_LIVE_PASS": live_binding.get("status") == "PASS",
        "CANONICAL_SOURCE_BINDING": (
            binding.get("code_manifest_sha256") == manifest_digest
            and str(binding.get("source_coverage_result_sha256", "")).upper()
            and binding.get("source_coverage_schema") == stored_source.get("schema")
            and binding.get("source_coverage_status") == "PROVED_IN_RESTRICTED_SOURCE_MODEL"
        ),
        "SEALED_CONTRACT": (
            coverage.get("baseline", {}).get("status") == "SEALED"
            and all_true(coverage.get("checks", {}))
        ),
        "PAYMENT_POTENTIAL": (
            baseline.get("status") == "CERTIFIED"
            and baseline.get("target") == 10
            and baseline.get("circuit_value") == 10
            and baseline.get("potential_verified") is True
        ),
        "PAYMENT_DECOMPOSABLE": (
            baseline.get("decomposable") is True
            and not baseline.get("duplicate_resources")
        ),
        "FREE_BYPASS_REFUTED": (
            capability.get("bypass_fixture", {}).get("status") == "REFUTED_BY_DERIVATION"
            and capability.get("bypass_fixture", {}).get("circuit_value") == 0
        ),
        "SHARED_DEBIT_WITHHELD": (
            capability.get("shared_debit_fixture", {}).get("status") == "NONDECOMPOSABLE"
            and capability.get("shared_debit_fixture", {}).get("decomposable") is False
        ),
        "LEDGER_AND_CATALOG_INTEGRATION": (
            canonical.get("run_passed") is True
            and all_true(canonical.get("checks", {}))
            and quantities.get("theory_cover") == 10
            and quantities.get("catalog_certificate") == 10
            and quantities.get("observed_minimum") == 10
            and quantities.get("baseline_execution_floor") == 10
            and route_catalog.get("routes_enumerated") == 840
            and route_catalog.get("complete_for_declared_first_four_route_grammar") is True
            and route_catalog.get("minimizing_routes") == 24
        ),
        "OUTAGE_FAILS_CLOSED": all_true(outage.get("checks", {})),
        "RECOVERY_SUCCEEDS": all_true(recovery.get("checks", {})),
        "OUTAGE_FINAL_BINDING": (
            outage_binding.get("code_manifest_sha256") == manifest_digest
            and outage_binding.get("canonical_result_sha256") == canonical_result_sha256
        ),
        "RECOVERY_FINAL_BINDING": (
            recovery_binding.get("code_manifest_sha256") == manifest_digest
            and recovery_binding.get("canonical_result_sha256") == canonical_result_sha256
        ),
        "MINIMIZING_EXECUTION_REALIZES_VALUE": (
            quantities.get("observed_minimum") == baseline.get("circuit_value") == 10
        ),
        "SCOPE_DOES_NOT_OVERCLAIM": (
            canonical.get("scope", {}).get("deployment_wide") is False
            and canonical.get("scope", {}).get("hardware_non_exportability_proved") is False
            and canonical.get("scope", {}).get("independent_economic_operators_claimed") is False
        ),
    }

    passed = all(checks.values())
    result = {
        "schema": "ptr-end-to-end-finite-language-certificate/v1",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "certificate": {
            "language": "declared finite two-host service language",
            "certification_outcome": {"status": "CERTIFIED" if passed else "UNKNOWN", "floor": 10 if passed else 0},
            "named_acquirer_outflow_lower_bound": 10 if passed else 0,
            "named_acquirer_outflow_exact_value": 10 if passed else None,
            "exactness_basis": "verified lower-bound potential plus an observed minimizing execution",
            "deployment_wide": False,
        },
        "proof_chain": [
            "the RSP-V6 soundness derivation proves the source-level producer, secret-flow, lifecycle, and delivery-root obligations",
            "the sealed component contract supplies the remaining typed composition premises",
            "ledger-derived leaf floors and allocation witnesses establish decomposable payment supports",
            "the verified potential proves the lower bound",
            "the minimizing execution proves exactness inside the declared language",
        ],
        "input_sha256": {
            name: sha256_file(path)
            for name, path in paths.items()
            if path.is_file()
        },
        "not_claimed": [
            "deployment-wide route closure",
            "hardware non-exportability",
            "seven independent economic operators",
            "a measured bribery or acquisition price",
            "operating-system or interpreter integrity",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    width = max(len(name) for name in checks)
    for name, ok in checks.items():
        print(f"{name.ljust(width)}  {'PASS' if ok else 'FAIL'}")
    print(f"FINITE_LANGUAGE_PAYMENT_STATUS={result['certificate']['certification_outcome']['status']}")
    print(f"FINITE_LANGUAGE_PAYMENT_FLOOR={result['certificate']['certification_outcome']['floor']}")
    print(f"FINITE_LANGUAGE_PAYMENT_EXACT={result['certificate']['named_acquirer_outflow_exact_value']}")
    print(f"END_TO_END_CERTIFICATE={result['status']}")
    print(f"END_TO_END_CERTIFICATE_RESULT={args.output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())