#!/usr/bin/env python3
"""Validate the supplied Dune exports without treating them as security bounds."""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "dune" / "raw"
RESULTS = ROOT / "results"


def rows(name: str) -> list[dict[str, str]]:
    with (RAW / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def d(value: str) -> Decimal:
    return Decimal(value)


def close(left: Decimal, right: Decimal, tolerance: Decimal = Decimal("1e-12")) -> bool:
    return abs(left - right) <= tolerance


def main() -> None:
    checks: list[tuple[str, bool, str]] = []
    summary = rows("01_settlement_tx_count_summary.csv")[0]
    daily = rows("02_daily_settlement_tx_count.csv")
    transfer = rows("03_transfer_join_coverage.csv")[0]
    curve = rows("certificate_coverage_curve.csv")
    selected = rows("04_empirical_target_coverage_selected.csv")
    dex = rows("07_dex_trades_aggregate_stats.csv")[0]

    settlement_count = d(summary["settlement_tx_count"])
    daily_sum = sum(d(row["settlement_tx_count"]) for row in daily)
    checks.append(("daily_sum_matches_summary", daily_sum == settlement_count, str(daily_sum)))

    transfer_count = d(transfer["settlement_txs"])
    checks.append(
        ("transfer_count_matches_summary", transfer_count == settlement_count, str(transfer_count))
    )
    transfer_ratio = d(transfer["txs_with_transfer_match"]) / transfer_count
    checks.append(
        (
            "transfer_coverage_ratio",
            close(transfer_ratio, d(transfer["tx_transfer_coverage"])),
            str(transfer_ratio),
        )
    )
    usd_ratio = d(transfer["txs_with_amount_usd"]) / transfer_count
    checks.append(
        ("transfer_usd_coverage_ratio", close(usd_ratio, d(transfer["tx_usd_coverage"])), str(usd_ratio))
    )

    thresholds = [d(row["certified_per_keyper_resistance_usd"]) for row in curve]
    coverage = [d(row["empirical_certificate_coverage"]) for row in curve]
    checks.append(
        ("curve_thresholds_strictly_increasing", all(a < b for a, b in zip(thresholds, thresholds[1:])), str(len(curve)))
    )
    checks.append(
        ("curve_coverage_nondecreasing", all(a <= b for a, b in zip(coverage, coverage[1:])), str(len(curve)))
    )

    curve_by_threshold = {
        row["certified_per_keyper_resistance_usd"]: row for row in curve
    }
    selected_match = True
    for row in selected:
        candidate = curve_by_threshold.get(row["certified_per_keyper_resistance_usd"])
        if candidate is None:
            selected_match = False
            break
        for field in (
            "total_stress_targets",
            "covered_stress_targets",
            "empirical_certificate_coverage",
            "empirical_certificate_coverage_pct",
        ):
            if d(row[field]) != d(candidate[field]):
                selected_match = False
                break
    checks.append(("selected_rows_match_curve", selected_match, str(len(selected))))

    dex_settlements = d(dex["settlement_txs"])
    dex_with_usd = d(dex["txs_with_usd"])
    checks.append(("dex_usd_count_bounded", dex_with_usd <= dex_settlements, str(dex_with_usd)))
    dex_pct = Decimal(100) * dex_with_usd / dex_settlements
    checks.append(("dex_usd_coverage_ratio", close(dex_pct, d(dex["tx_usd_coverage_pct"])), str(dex_pct)))
    quantiles = [d(dex[field]) for field in ("p50_usd", "p90_usd", "p95_usd", "p99_usd")]
    checks.append(("dex_quantiles_ordered", all(a <= b for a, b in zip(quantiles, quantiles[1:])), ";".join(map(str, quantiles))))

    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "dune_validation.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["check", "passed", "detail"])
        writer.writerows(checks)

    summary_rows = [
        ("transfer_join", "settlement_txs", settlement_count, "transactions", "01_settlement_tx_count_summary.csv"),
        ("transfer_join", "tx_usd_coverage", d(transfer["tx_usd_coverage"]), "fraction", "03_transfer_join_coverage.csv"),
        ("dex_trades", "settlement_txs", dex_settlements, "transactions", "07_dex_trades_aggregate_stats.csv"),
        ("dex_trades", "total_usd_notional_proxy", d(dex["total_usd_notional_proxy"]), "USD proxy", "07_dex_trades_aggregate_stats.csv"),
        ("dex_trades", "p50_usd", d(dex["p50_usd"]), "USD proxy", "07_dex_trades_aggregate_stats.csv"),
        ("dex_trades", "p90_usd", d(dex["p90_usd"]), "USD proxy", "07_dex_trades_aggregate_stats.csv"),
        ("dex_trades", "p95_usd", d(dex["p95_usd"]), "USD proxy", "07_dex_trades_aggregate_stats.csv"),
        ("dex_trades", "p99_usd", d(dex["p99_usd"]), "USD proxy", "07_dex_trades_aggregate_stats.csv"),
    ]
    for row in selected:
        summary_rows.append(
            (
                "historical_target_calibration",
                f"coverage_at_per_keyper_{row['certified_per_keyper_resistance_usd']}_usd",
                d(row["empirical_certificate_coverage"]),
                "historical fraction",
                "04_empirical_target_coverage_selected.csv",
            )
        )
    with (RESULTS / "dune_calibration_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["dataset_family", "metric", "value", "unit", "source_file", "interpretation"])
        for row in summary_rows:
            writer.writerow((*row, "CALIBRATION_ONLY_NOT_VALUE_CAP"))

    failures = sum(not passed for _, passed, _ in checks)
    print(f"dune_validation_checks={len(checks)}")
    print(f"dune_validation_failures={failures}")
    print(f"dune_selected_coverage_rows={len(selected)}")
    print("dune_interpretation=CALIBRATION_ONLY_NOT_VALUE_CAP")
    if failures:
        raise SystemExit("one or more Dune validation checks failed")


if __name__ == "__main__":
    main()
