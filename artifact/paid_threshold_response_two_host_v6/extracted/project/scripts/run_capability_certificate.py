"""Emit the capability certificate for the two-host committee (WP5/WP6).

Reads the public committee bundle, builds the payment-capability circuit, and
writes ``capability_certificate.v3.json`` containing:

* the baseline certificate (root value, verified potential, minimum derivation);
* the bypass fixture (a free branch, REFUTED_BY_DERIVATION at target 10);
* the shared-debit fixture (NONDECOMPOSABLE, not summed);
* the 840 -> 35 -> 1 route compression.

It does not touch the network; the circuit's leaf floors are the committee's
declared response floors, exactly the quantities the two-host run certifies.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.checker import (  # noqa: E402
    build_two_host_circuit,
    certify,
    route_compression,
    with_free_bypass,
    with_shared_debit,
)
from ptr_v3.experiment import Committee  # noqa: E402
from ptr_v3.utils import write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit the two-host capability certificate.")
    parser.add_argument("--committee", type=Path, default=ROOT / "config" / "committee.public.v3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "capability_certificate.v3.json")
    args = parser.parse_args()

    committee = Committee.from_file(args.committee)
    floors = list(committee.response_floors)
    threshold = committee.threshold
    cover = sum(sorted(floors)[:threshold])

    base = build_two_host_circuit(floors, threshold)
    baseline = certify(base, target=cover)
    bypass = certify(with_free_bypass(base), target=cover)
    shared = certify(with_shared_debit(base, 1, 2), target=cover)
    compression = route_compression(committee.committee_size, threshold)

    result = {
        "schema": "paid-threshold-response-two-host-capability/v5",
        "committee": {"size": committee.committee_size, "threshold": threshold, "floors": floors},
        "cover": cover,
        "baseline": baseline.to_dict(),
        "bypass_fixture": bypass.to_dict(),
        "shared_debit_fixture": shared.to_dict(),
        "route_compression": compression,
        "checks": {
            "baseline_certified_at_cover": baseline.status == "CERTIFIED" and baseline.circuit_value == cover,
            "baseline_potential_verified": baseline.potential_verified,
            "bypass_refutes_cover": bypass.status == "REFUTED_BY_DERIVATION" and bypass.circuit_value == 0,
            "shared_debit_nondecomposable": shared.status == "NONDECOMPOSABLE",
            "compression_840_35_1": (
                compression["ordered_routes"] == 840
                and compression["coalition_derivations"] == 35
                and compression["threshold_nodes"] == 1
            ),
        },
    }
    write_json(args.output, result)

    print(f"CAPABILITY_CERTIFICATE={args.output}")
    print(f"BASELINE_STATUS={baseline.status}  ROOT_VALUE={baseline.circuit_value}  POTENTIAL_VERIFIED={baseline.potential_verified}")
    print(f"BYPASS_STATUS={bypass.status}  ROOT_VALUE={bypass.circuit_value}")
    print(f"SHARED_DEBIT_STATUS={shared.status}")
    print(f"ROUTE_COMPRESSION={compression['ordered_routes']}->{compression['coalition_derivations']}->{compression['threshold_nodes']}")
    failed = [k for k, v in result["checks"].items() if not v]
    if failed:
        print("FAILED_CHECKS=" + ",".join(sorted(failed)))
        return 1
    print("CAPABILITY_CERTIFICATE_RUN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
