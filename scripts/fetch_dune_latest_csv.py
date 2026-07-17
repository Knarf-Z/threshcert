#!/usr/bin/env python3
"""Optional Dune refresh helper. It is not used by deterministic reproduction."""
from __future__ import annotations

import argparse
import os
import urllib.request
from pathlib import Path


QUERIES = {
    7714633: "01_settlement_tx_count_summary.csv",
    7714683: "02_daily_settlement_tx_count.csv",
    7714701: "03_transfer_join_coverage.csv",
    7715186: "certificate_coverage_curve.csv",
    7715248: "05_top_token_symbols.csv",
    7715263: "06_top_notional_outliers.csv",
    7899253: "07_dex_trades_aggregate_stats.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    api_key = os.environ.get("DUNE_API_KEY")
    if not api_key:
        raise SystemExit("DUNE_API_KEY is not set")
    args.outdir.mkdir(parents=True, exist_ok=True)

    for query_id, filename in QUERIES.items():
        destination = args.outdir / filename
        if destination.exists() and not args.force:
            raise SystemExit(f"refusing to overwrite {destination}; use --force")
        request = urllib.request.Request(
            f"https://api.dune.com/api/v1/query/{query_id}/results/csv",
            headers={"X-Dune-API-Key": api_key},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            destination.write_bytes(response.read())
        print(f"wrote {destination}")


if __name__ == "__main__":
    main()
