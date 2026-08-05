from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_exp.experiment import run_to_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the paid threshold response experiment on Host 1.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "host1.json")
    parser.add_argument("--canonical", type=Path, default=ROOT / "results" / "canonical_result.v2.json")
    parser.add_argument("--metadata", type=Path, default=ROOT / "results" / "run_metadata.v2.json")
    args = parser.parse_args()

    canonical = run_to_file(
        args.config.resolve(), args.canonical.resolve(), args.metadata.resolve(), ROOT / "src"
    )
    quantities = canonical["quantities"]
    catalog = canonical["route_catalog"]
    checks = canonical["checks"]
    failed = [name for name, passed in checks.items() if not passed]

    print(f"CANONICAL_RESULT={args.canonical.resolve()}")
    print(f"RUN_METADATA={args.metadata.resolve()}")
    print(f"THEORY_COVER={quantities['theory_cover']}")
    print(f"CATALOG_CERTIFICATE={quantities['catalog_certificate']}")
    print(f"OBSERVED_MINIMUM={quantities['observed_minimum']}")
    print(f"ROUTES_ENUMERATED={catalog['routes_enumerated']}")
    print(f"ALL_ROUTE_FLOORS_LEDGER_DERIVED={str(catalog['all_floors_ledger_derived']).lower()}")
    print(f"MINIMIZING_ROUTES={catalog['minimizing_routes']}")
    print(f"EXPENSIVE_COALITION_4567_EXECUTION_FLOOR={catalog['coalition_floors'].get('4,5,6,7')}")
    print(f"BASELINE_STATUS={canonical['baseline']['report']['status']}")
    print(f"MULTIPROCESS_WORKERS={canonical['multiprocess_smoke']['distinct_worker_count']}")
    if failed:
        print("FAILED_CHECKS=" + ",".join(sorted(failed)))
        return 1
    print("HOST1_EXPERIMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
