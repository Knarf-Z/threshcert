#!/usr/bin/env python3
"""Deterministic experiment for epoch erasure and refresh-window certificates."""
from __future__ import annotations

import itertools
import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "refresh_window_experiment.json"


def subsets_within(latencies: list[int], duration: int):
    n = len(latencies)
    for mask in range(1 << n):
        members = tuple(i for i in range(n) if mask & (1 << i))
        if sum(latencies[i] for i in members) <= duration:
            yield mask, members


def local_epoch_cost(
    costs: list[int], latencies: list[int], threshold: int, duration: int
) -> int | None:
    candidates = [
        sum(costs[i] for i in members)
        for _, members in subsets_within(latencies, duration)
        if len(members) >= threshold
    ]
    return min(candidates) if candidates else None


def erasure_window_cost(
    costs: list[int], latencies: list[int], threshold: int, durations: list[int]
) -> int | None:
    candidates = [
        local_epoch_cost(costs, latencies, threshold, duration)
        for duration in durations
    ]
    finite = [value for value in candidates if value is not None]
    return min(finite) if finite else None


def persistent_window_cost(
    costs: list[int], latencies: list[int], threshold: int, durations: list[int]
) -> int | None:
    states: dict[int, int] = {0: 0}
    options = [list(subsets_within(latencies, duration)) for duration in durations]
    for epoch_options in options:
        next_states: dict[int, int] = {}
        for current_mask, current_cost in states.items():
            for chosen_mask, _ in epoch_options:
                new_mask = current_mask | chosen_mask
                newly_paid = chosen_mask & ~current_mask
                new_cost = current_cost + sum(
                    costs[i] for i in range(len(costs)) if newly_paid & (1 << i)
                )
                next_states[new_mask] = min(next_states.get(new_mask, math.inf), new_cost)
        states = next_states
    candidates = [cost for mask, cost in states.items() if mask.bit_count() >= threshold]
    return min(candidates) if candidates else None


def fmt(value: int | None) -> str:
    return "INF" if value is None else str(value)


def paired_world() -> dict[str, object]:
    costs = [1] * 7
    latencies = [2] * 7
    durations = [6, 6]
    return {
        "costs": costs,
        "latencies": latencies,
        "threshold": 4,
        "epochDurations": durations,
        "sameSnapshotLedgers": True,
        "erasureWorldCost": fmt(erasure_window_cost(costs, latencies, 4, durations)),
        "persistentWorldCost": fmt(
            persistent_window_cost(costs, latencies, 4, durations)
        ),
        "interpretation": "snapshot ledgers do not identify cross-epoch compatibility",
    }


def duration_ladder() -> list[dict[str, object]]:
    costs = [1, 1, 1, 1, 5, 5, 5]
    latencies = [3, 3, 3, 3, 1, 1, 1]
    rows = []
    for duration in (4, 6, 8, 10, 12):
        rows.append(
            {
                "duration": duration,
                "erasureCost": fmt(local_epoch_cost(costs, latencies, 4, duration)),
            }
        )
    return rows


def randomized_monotonicity(
    trials: int = 5_000, seed: int = 20260802
) -> dict[str, object]:
    rng = random.Random(seed)
    checked = 0
    mismatches = 0
    decomposition_mismatches = 0
    for _ in range(trials):
        n = rng.randint(4, 9)
        threshold = rng.randint(2, n)
        costs = [rng.randint(1, 20) for _ in range(n)]
        latencies = [rng.randint(1, 5) for _ in range(n)]
        short = rng.randint(1, 10)
        long = rng.randint(short, 16)
        short_cost = local_epoch_cost(costs, latencies, threshold, short)
        long_cost = local_epoch_cost(costs, latencies, threshold, long)
        short_rank = math.inf if short_cost is None else short_cost
        long_rank = math.inf if long_cost is None else long_cost
        if short_rank < long_rank:
            mismatches += 1
        durations = [rng.randint(1, 16) for _ in range(rng.randint(1, 5))]
        explicit = min(
            (
                value
                for value in (
                    local_epoch_cost(costs, latencies, threshold, duration)
                    for duration in durations
                )
                if value is not None
            ),
            default=None,
        )
        if erasure_window_cost(costs, latencies, threshold, durations) != explicit:
            decomposition_mismatches += 1
        checked += 1
    return {
        "seed": seed,
        "trials": trials,
        "durationMonotonicityMismatches": mismatches,
        "erasureDecompositionMismatches": decomposition_mismatches,
    }


def build_result() -> dict[str, object]:
    return {
        "schema": "fc-refresh-window-experiment-v1",
        "claimBoundary": {
            "erasureRequiredForSnapshotInfimum": True,
            "latencyEvidenceRequiredForRefreshBenefit": True,
            "unknownCrossEpochCompatibility": "WINDOW_CERTIFICATE_NOT_IDENTIFIED",
        },
        "pairedWorld": paired_world(),
        "durationLadder": duration_ladder(),
        "randomizedChecks": randomized_monotonicity(),
    }


def main() -> None:
    result = build_result()
    paired = result["pairedWorld"]
    if paired["erasureWorldCost"] != "INF" or paired["persistentWorldCost"] != "4":
        raise SystemExit("refresh paired-world check failed")
    if [row["erasureCost"] for row in result["durationLadder"]] != [
        "INF",
        "16",
        "12",
        "8",
        "4",
    ]:
        raise SystemExit("refresh duration ladder mismatch")
    checks = result["randomizedChecks"]
    if (
        checks["durationMonotonicityMismatches"]
        or checks["erasureDecompositionMismatches"]
    ):
        raise SystemExit("refresh randomized check failed")
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("refresh_window_schema=fc-refresh-window-experiment-v1")
    print(f"paired_erasure_cost={paired['erasureWorldCost']}")
    print(f"paired_persistent_cost={paired['persistentWorldCost']}")
    print(
        "duration_ladder="
        + ",".join(f"{row['duration']}:{row['erasureCost']}" for row in result["durationLadder"])
    )
    checks = result["randomizedChecks"]
    print(
        f"duration_monotonicity={checks['trials'] - checks['durationMonotonicityMismatches']}/"
        f"{checks['trials']}"
    )
    print(
        f"erasure_decomposition={checks['trials'] - checks['erasureDecompositionMismatches']}/"
        f"{checks['trials']}"
    )
    print("refresh_window_experiment=PASS")


if __name__ == "__main__":
    main()
