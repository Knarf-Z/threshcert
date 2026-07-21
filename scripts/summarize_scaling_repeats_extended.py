#!/usr/bin/env python3
"""Summarize the ten n=20 repeat files into one median/IQR row.

Mirrors `summarize_scaling_repeats.py`'s discipline for the original
n=8..18 table, kept as a wholly separate script/output so that script's
exact 10-files-by-6-rows assertion (and the byte-compared consumer in
`extended_experiments/`) is never touched.
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "solver_scaling_repeats_extended"
OUTPUT = ROOT / "results" / "solver_scaling_repeats_extended_summary.csv"


def main() -> None:
    paths = sorted(RAW.glob("solver_scaling_run_*.csv"))
    if len(paths) != 10:
        raise SystemExit(f"expected 10 repeat files, found {len(paths)}")
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != 1:
            raise SystemExit(f"{path.name}: expected 1 row, found {len(rows)}")
        for row in rows:
            grouped[int(row["n"])].append(row)

    fields = [
        "n", "runs", "subset_states", "min_seconds", "q1_seconds",
        "median_seconds", "q3_seconds", "max_seconds", "mean_seconds",
        "peak_mib", "optimum",
    ]
    output_rows: list[dict[str, str]] = []
    for n in sorted(grouped):
        rows = grouped[n]
        if len(rows) != 10:
            raise SystemExit(f"n={n}: expected 10 runs, found {len(rows)}")
        for field in ("subset_states", "optimum"):
            if len({row[field] for row in rows}) != 1:
                raise SystemExit(f"n={n}: inconsistent {field}")
        seconds = [float(row["wall_seconds"]) for row in rows]
        q1, _, q3 = statistics.quantiles(seconds, n=4, method="inclusive")
        peak_values = [float(row["peak_mib"]) for row in rows]
        peak_spread = max(peak_values) - min(peak_values)
        if peak_spread > 0.01:
            # `peak_mib` is expected to vary by a few bytes across repeats
            # (allocator warm-up on the first process invocation); a large
            # spread would signal a real measurement problem instead.
            raise SystemExit(f"n={n}: peak_mib spread too large ({peak_spread:.6f} MiB)")
        output_rows.append({
            "n": str(n),
            "runs": "10",
            "subset_states": rows[0]["subset_states"],
            "min_seconds": f"{min(seconds):.9f}",
            "q1_seconds": f"{q1:.9f}",
            "median_seconds": f"{statistics.median(seconds):.9f}",
            "q3_seconds": f"{q3:.9f}",
            "max_seconds": f"{max(seconds):.9f}",
            "mean_seconds": f"{statistics.mean(seconds):.9f}",
            "peak_mib": f"{statistics.median(peak_values):.9f}",
            "optimum": f"{float(rows[0]['optimum']):.12f}",
        })
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    n20 = next(row for row in output_rows if row["n"] == "20")
    print(f"scaling_repeat_extended_files={len(paths)}")
    print(f"n20_median_seconds={n20['median_seconds']}")
    print(f"n20_q1_seconds={n20['q1_seconds']}")
    print(f"n20_q3_seconds={n20['q3_seconds']}")


if __name__ == "__main__":
    main()
