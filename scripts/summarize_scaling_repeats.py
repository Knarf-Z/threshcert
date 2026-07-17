#!/usr/bin/env python3
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "solver_scaling_repeats"
OUTPUT = ROOT / "results" / "solver_scaling_repeats_summary.csv"


def main() -> None:
    paths = sorted(RAW.glob("solver_scaling_run_*.csv"))
    if len(paths) != 10:
        raise SystemExit(f"expected 10 repeat files, found {len(paths)}")
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != 6:
            raise SystemExit(f"{path.name}: expected 6 rows, found {len(rows)}")
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
        for field in ("subset_states", "peak_mib", "optimum"):
            if len({row[field] for row in rows}) != 1:
                raise SystemExit(f"n={n}: inconsistent {field}")
        seconds = [float(row["wall_seconds"]) for row in rows]
        q1, _, q3 = statistics.quantiles(seconds, n=4, method="inclusive")
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
            "peak_mib": f"{float(rows[0]['peak_mib']):.9f}",
            "optimum": f"{float(rows[0]['optimum']):.12f}",
        })
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    n18 = next(row for row in output_rows if row["n"] == "18")
    print(f"scaling_repeat_files={len(paths)}")
    print(f"n18_median_seconds={n18['median_seconds']}")
    print(f"n18_q1_seconds={n18['q1_seconds']}")
    print(f"n18_q3_seconds={n18['q3_seconds']}")


if __name__ == "__main__":
    main()
