#!/usr/bin/env python3
"""Reproduce the deterministic controlled checks reported in the paper."""
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def activation_ladder() -> None:
    rows = []
    for r in range(5):
        tc = 5
        ac = 10 * r + (5 - r)
        rows.append((r, r / 10, tc, ac, ac / tc))
    with (RESULTS / "activation_ladder.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["r", "seed_exposure", "TC", "AC", "AC_over_TC"])
        w.writerows(rows)


def mechanism_scope() -> None:
    rows = []
    for k in [1, 2, 4, 8]:
        rows.append((k, k + 4, "infinity", 4, 4))
    with (RESULTS / "mechanism_scope.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["k", "sequential", "simultaneous", "package", "robust_TC"])
        w.writerows(rows)


def allocation_table() -> None:
    # Member order fixes all heuristic ties: d1, d2, b1, ..., b6.
    member_names = ["d1", "d2", "b1", "b2", "b3", "b4", "b5", "b6"]
    resistances = [0.5, 0.5, 2, 2, 2, 2, 2, 2]
    covers = [
        (2, 3, 4),  # b1, b2, b3
        (2, 5, 6),  # b1, b4, b5
        (3, 5, 7),  # b2, b4, b6
        (4, 6, 7),  # b3, b5, b6
    ]

    def cover_costs(increments: list[int]) -> list[float]:
        return [sum(resistances[i] + increments[i] for i in cover) for cover in covers]

    def cheapest_current(budget: int) -> list[int]:
        increments = [0] * len(member_names)
        for _ in range(budget):
            chosen = min(
                range(len(member_names)),
                key=lambda i: (resistances[i] + increments[i], i),
            )
            increments[chosen] += 1
        return increments

    def weight_cycle(budget: int) -> list[int]:
        # Nonincreasing weight order is already d1, d2, b1, ..., b6.
        increments = [0] * len(member_names)
        for unit in range(budget):
            increments[unit % len(member_names)] += 1
        return increments

    def integer_allocations(total: int, count: int, prefix: tuple[int, ...] = ()):
        if count == 1:
            yield prefix + (total,)
            return
        for first in range(total + 1):
            yield from integer_allocations(total - first, count - 1, prefix + (first,))

    def bottleneck_exact(budget: int) -> list[int]:
        best_value = float("-inf")
        best: tuple[int, ...] | None = None
        for candidate in integer_allocations(budget, len(member_names)):
            value = min(cover_costs(list(candidate)))
            if value > best_value:
                best_value = value
                best = candidate
        if best is None:
            raise AssertionError("allocation enumeration returned no candidate")
        return list(best)

    strategies = {
        "cheapest_resistance": cheapest_current,
        "largest_weight": weight_cycle,
        "bottleneck": bottleneck_exact,
    }
    budgets = [0, 2, 4, 6, 8, 10]
    details = []
    summary = []
    for budget in budgets:
        summary_row: list[float | int] = [budget]
        for strategy, allocate in strategies.items():
            increments = allocate(budget)
            costs = cover_costs(increments)
            certificate = min(costs)
            summary_row.append(certificate)
            details.append(
                (
                    budget,
                    strategy,
                    certificate,
                    *increments,
                    *costs,
                )
            )
        summary.append(tuple(summary_row))

    with (RESULTS / "defensive_allocation.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["budget", "strategy", "certificate"]
            + [f"h_{name}" for name in member_names]
            + ["cover_1", "cover_2", "cover_3", "cover_4"]
        )
        w.writerows(details)

    with (RESULTS / "defensive_allocation_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow(["budget", *strategies.keys()])
        w.writerows(summary)


def sensitivity() -> None:
    rows = []
    other_three = 2700 + 2800 + 3000
    for p1 in [0.60, 0.50, 0.40, 0.30, 0.20, 0.10, 0.00]:
        r1 = 1000 + p1 * 5000
        certificate = r1 + other_three
        rows.append((p1, r1, certificate, "ACCEPT" if certificate >= 10000 else "REJECT"))
    with (RESULTS / "enforceability_sensitivity.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["p1", "R1", "certificate", "decision_at_10000"])
        w.writerows(rows)


if __name__ == "__main__":
    activation_ladder()
    mechanism_scope()
    allocation_table()
    sensitivity()
    print("wrote controlled check outputs to", RESULTS)
