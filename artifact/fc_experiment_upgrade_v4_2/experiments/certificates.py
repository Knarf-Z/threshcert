from __future__ import annotations

from itertools import combinations, permutations
from math import inf
from typing import Iterable, Sequence


def weight(indices: Iterable[int], weights: Sequence[float]) -> float:
    return sum(weights[i] for i in indices)


def threshold_cover(
    resistance: Sequence[float],
    weights: Sequence[float],
    threshold: float,
    initial: Iterable[int] = (),
) -> float:
    initial = frozenset(initial)
    if weight(initial, weights) >= threshold:
        return 0.0
    remaining = [i for i in range(len(weights)) if i not in initial]
    best = inf
    for size in range(len(remaining) + 1):
        for selected in combinations(remaining, size):
            if weight(initial | frozenset(selected), weights) >= threshold:
                best = min(best, sum(resistance[i] for i in selected))
    return best


def order_feasible(
    order: Sequence[int],
    weights: Sequence[float],
    activation: Sequence[float],
    constrained: frozenset[int],
    initial: frozenset[int],
) -> bool:
    exposure = weight(initial, weights)
    for member in order:
        if member in constrained and exposure + 1e-12 < activation[member]:
            return False
        exposure += weights[member]
    return True


def mixed_cover(
    resistance: Sequence[float],
    weights: Sequence[float],
    threshold: float,
    activation: Sequence[float],
    constrained: Iterable[int],
    initial: Iterable[int] = (),
) -> float:
    initial = frozenset(initial)
    constrained = frozenset(constrained) - initial
    if weight(initial, weights) >= threshold:
        return 0.0
    remaining = [i for i in range(len(weights)) if i not in initial]
    best = inf
    for size in range(1, len(remaining) + 1):
        for selected in combinations(remaining, size):
            if weight(initial | frozenset(selected), weights) < threshold:
                continue
            if any(
                order_feasible(order, weights, activation, constrained, initial)
                for order in permutations(selected)
            ):
                best = min(best, sum(resistance[i] for i in selected))
    return best


def mabc(
    resistance: Sequence[float],
    weights: Sequence[float],
    threshold: float,
    activation: Sequence[float],
    constrained: Iterable[int],
    package_budget: int,
    initial: Iterable[int] = (),
) -> float:
    initial = frozenset(initial)
    remaining = [i for i in range(len(weights)) if i not in initial]
    constrained = frozenset(constrained)
    best = inf
    for size in range(min(package_budget, len(remaining)) + 1):
        for package in combinations(remaining, size):
            package = frozenset(package)
            remainder_cost = mixed_cover(
                resistance,
                weights,
                threshold,
                activation,
                constrained - package,
                initial | package,
            )
            best = min(
                best,
                sum(resistance[i] for i in package) + remainder_cost,
            )
    return best
