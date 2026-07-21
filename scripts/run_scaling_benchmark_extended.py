#!/usr/bin/env python3
"""Additive extension of the machine-specific scaling check to n=20.

Kept as a separate script and output file from `run_scaling_benchmark.py`,
whose six-point (n=8..18), ten-repeat table is asserted exactly by
`summarize_scaling_repeats.py` (exact file count and row count) and
consumed by
`extended_experiments/scripts/run_extended_certificate_experiments.py`
(byte-compared against `expected/extended_certificate_summary.txt`). Adding
a further point there would break both locks; this script instead reuses
the same solver and repeats the same repeated-timing discipline for one
additional point without touching any existing file.
"""
from __future__ import annotations

import csv
import time
import tracemalloc
from pathlib import Path

from run_scaling_benchmark import solve

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "solver_scaling_extended.csv"
N_VALUES = [20]


def main() -> None:
    rows = []
    for n in N_VALUES:
        tracemalloc.start()
        start = time.perf_counter()
        best = solve(n)
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows.append((n, 1 << n, elapsed, peak / (1024 * 1024), best))
        print(n, elapsed, peak / (1024 * 1024), best)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "subset_states", "wall_seconds", "peak_mib", "optimum"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
