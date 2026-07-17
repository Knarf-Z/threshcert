#!/usr/bin/env python3
"""Machine-specific scaling check for an exact subset-state activation solver."""
from __future__ import annotations
import csv
import math
import random
import time
import tracemalloc
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "solver_scaling.csv"


def solve(n: int, seed: int = 20260711) -> float:
    rng = random.Random(seed + n)
    weights = [1.0 / n] * n
    resistances = [1.0 + rng.random() * 9.0 for _ in range(n)]
    # A deterministic activation pattern with several initially available seeds.
    taus = [0.0 if i < max(2, n // 5) else ((i % 4) / n) for i in range(n)]
    threshold = math.ceil(n / 2) / n
    size = 1 << n
    reachable = bytearray(size)
    reachable[0] = 1
    exposure = array("d", [0.0]) * size
    cost = array("d", [0.0]) * size
    best = math.inf
    full_mask = size - 1
    for mask in range(size):
        if not reachable[mask]:
            continue
        alpha = exposure[mask]
        if alpha + 1e-12 >= threshold:
            if cost[mask] < best:
                best = cost[mask]
            continue
        remaining = full_mask ^ mask
        while remaining:
            bit = remaining & -remaining
            i = bit.bit_length() - 1
            if alpha + 1e-12 >= taus[i]:
                nxt = mask | bit
                if not reachable[nxt]:
                    reachable[nxt] = 1
                    exposure[nxt] = alpha + weights[i]
                    cost[nxt] = cost[mask] + resistances[i]
            remaining ^= bit
    return best


def main() -> None:
    rows = []
    for n in [8, 10, 12, 14, 16, 18]:
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
