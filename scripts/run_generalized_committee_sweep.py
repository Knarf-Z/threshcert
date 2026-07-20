#!/usr/bin/env python3
"""Generalize the seeded random four-of-seven checks to other committee shapes.

The original 100-seed monotonicity, truncation-error, and greedy-allocation
checks in ``run_lattice_mobius_experiments.py`` are fixed at n=7, q=4. This
script repeats the same checks at several other ``(n, q)`` shapes with a
similar threshold ratio, so the qualitative findings are not read as an
artifact of the one committee size the paper headlines. It is additive: it
does not modify or rerun the original n=7 experiment or its recorded outputs.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

from defense_lattice import (
    exact_budget_maximizer,
    is_monotone,
    marginal_greedy,
    mobius_transform,
    uniform_threshold_certificate,
    zeta_transform,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
RANDOM_TRIALS = 100
RANDOM_SEED = 20260714
COMMITTEE_SHAPES = [(5, 3), (9, 5), (11, 6), (13, 7)]
MAX_ORDERS = (1, 2, 3)


def write_rows(path: Path, header: list[str], rows: list[tuple[object, ...]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def truncated_values_by_order(
    coefficients: list[float], n: int, max_orders: tuple[int, ...]
) -> dict[int, list[float]]:
    """Return, for each requested max_order, the truncated value at every mask.

    Computed as a running sum of per-order zeta transforms rather than the
    O(3^n) per-mask subset enumeration used for the single n=7 case in
    ``defense_lattice.truncated_value``, so the same check stays cheap up to
    n=13 (O(max_order * n * 2^n) instead).
    """

    size = 1 << n
    highest = max(max_orders)
    layer_zetas = []
    for order in range(highest + 1):
        layer = [
            coefficients[mask] if mask.bit_count() == order else 0.0
            for mask in range(size)
        ]
        layer_zetas.append(zeta_transform(layer, n))

    running = [0.0] * size
    results: dict[int, list[float]] = {}
    for order in range(highest + 1):
        for mask in range(size):
            running[mask] += layer_zetas[order][mask]
        if order in max_orders:
            results[order] = list(running)
    return results


def run_shape(n: int, q: int) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    rng = random.Random(f"{RANDOM_SEED}-{n}-{q}")
    mobius_rows: list[tuple[object, ...]] = []
    allocation_rows: list[tuple[object, ...]] = []

    for trial in range(RANDOM_TRIALS):
        resistances = [1.0 + 9.0 * rng.random() for _ in range(n)]
        increments = [0.5 + 12.0 * rng.random() for _ in range(n)]
        values = [
            uniform_threshold_certificate(resistances, increments, mask, q)
            for mask in range(1 << n)
        ]
        monotone = is_monotone(values, n, tolerance=1e-10)
        coefficients = mobius_transform(values, n)
        truncated = truncated_values_by_order(coefficients, n, MAX_ORDERS)

        errors = {}
        for max_order in MAX_ORDERS:
            relative_errors = [
                abs(true_value - truncated[max_order][mask])
                / max(1.0, abs(true_value))
                for mask, true_value in enumerate(values)
            ]
            errors[max_order] = max(relative_errors)
        mobius_rows.append((n, q, trial, monotone, errors[1], errors[2], errors[3]))

        value = lambda mask: uniform_threshold_certificate(  # noqa: E731
            resistances, increments, mask, q
        )
        for budget in (1, 2, 3):
            _, exact_value = exact_budget_maximizer(value, n, budget)
            _, greedy_value = marginal_greedy(value, n, budget)
            gain_denominator = max(1e-12, exact_value - values[0])
            gain_ratio = (greedy_value - values[0]) / gain_denominator
            allocation_rows.append(
                (n, q, trial, budget, values[0], exact_value, greedy_value, gain_ratio)
            )

    return mobius_rows, allocation_rows


def main() -> None:
    all_mobius_rows: list[tuple[object, ...]] = []
    all_allocation_rows: list[tuple[object, ...]] = []
    monotonicity_failures_by_shape: dict[tuple[int, int], int] = {}

    for n, q in COMMITTEE_SHAPES:
        mobius_rows, allocation_rows = run_shape(n, q)
        all_mobius_rows.extend(mobius_rows)
        all_allocation_rows.extend(allocation_rows)
        monotonicity_failures_by_shape[(n, q)] = sum(
            1 for row in mobius_rows if not row[3]
        )

    write_rows(
        RESULTS / "mobius_generalized_sweep.csv",
        [
            "n",
            "q",
            "trial",
            "monotone",
            "max_relative_error_order1",
            "max_relative_error_order2",
            "max_relative_error_order3",
        ],
        all_mobius_rows,
    )
    write_rows(
        RESULTS / "allocation_generalized_sweep.csv",
        [
            "n",
            "q",
            "trial",
            "action_budget",
            "baseline",
            "exact_value",
            "greedy_value",
            "greedy_gain_ratio",
        ],
        all_allocation_rows,
    )

    if any(monotonicity_failures_by_shape.values()):
        raise SystemExit(
            f"monotonicity failed for shapes: {monotonicity_failures_by_shape}"
        )

    print(f"committee_shapes={len(COMMITTEE_SHAPES)}")
    print(f"trials_per_shape={RANDOM_TRIALS}")
    for n, q in COMMITTEE_SHAPES:
        print(f"shape_{n}_of_{q}_monotonicity_failures=0")
    for n, q in COMMITTEE_SHAPES:
        shape_ratios = [
            row[7]
            for row in all_allocation_rows
            if row[0] == n and row[1] == q and row[3] == 1
        ]
        print(f"shape_{n}_of_{q}_min_budget1_greedy_gain_ratio={min(shape_ratios):.6f}")
    print(f"random_seed={RANDOM_SEED}")
    print("generalized_committee_sweep=PASS")


if __name__ == "__main__":
    main()
