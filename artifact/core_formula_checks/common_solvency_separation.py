#!/usr/bin/env python3
"""Independent finite-state check of the paper's common-solvency separation."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import inf


def powerset(items: tuple[str, ...]):
    for size in range(len(items) + 1):
        yield from combinations(items, size)


def collateral(acquired: frozenset[str], seeds: frozenset[str], cores: frozenset[str]) -> int:
    seed_value = len(acquired & seeds)
    if seeds <= acquired:
        return seed_value + 2 * len(acquired & cores)
    return seed_value + (4 if cores <= acquired else 0)


def check_instance(k: int) -> tuple[int, int]:
    delta = Fraction(1, 4)
    threshold = 1 - delta
    seed_names = tuple(f"s{index}" for index in range(k))
    core_names = ("a", "b")
    members = seed_names + core_names
    seeds = frozenset(seed_names)
    cores = frozenset(core_names)
    weights = {
        **{seed: delta / k for seed in seed_names},
        "a": (1 - delta) / 2,
        "b": (1 - delta) / 2,
    }
    costs = {**{seed: 1 for seed in seed_names}, "a": 2, "b": 2}

    best: dict[frozenset[str], int] = {frozenset(): 0}
    frontier = [frozenset()]
    while frontier:
        acquired = frontier.pop()
        payment = best[acquired]
        for member in members:
            if member in acquired:
                continue
            next_set = acquired | {member}
            next_payment = payment + costs[member]
            if next_payment > collateral(next_set, seeds, cores):
                continue
            if next_payment < best.get(next_set, inf):
                best[next_set] = next_payment
                frontier.append(next_set)

    sequential = min(
        payment
        for acquired, payment in best.items()
        if sum((weights[member] for member in acquired), Fraction()) >= threshold
    )

    package = min(
        sum(costs[member] for member in subset)
        for raw_subset in powerset(members)
        for subset in [frozenset(raw_subset)]
        if sum((weights[member] for member in subset), Fraction()) >= threshold
        and sum(costs[member] for member in subset) <= collateral(subset, seeds, cores)
    )
    return sequential, package


for k in (1, 2, 3, 5, 8):
    sequential, package = check_instance(k)
    expected = (k + 4, 4)
    if (sequential, package) != expected:
        raise SystemExit(
            f"COMMON_SOLVENCY_SEPARATION=FAIL k={k} got={(sequential, package)} expected={expected}"
        )
    print(f"COMMON_SOLVENCY_INSTANCE=PASS k={k} sequential={sequential} package={package}")

print("COMMON_SOLVENCY_SEPARATION=PASS")