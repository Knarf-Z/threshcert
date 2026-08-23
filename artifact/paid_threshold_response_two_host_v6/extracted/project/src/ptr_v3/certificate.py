"""Four distinct quantities, computed by four distinct code paths.

``theory_cover``
    The closed form of Corollary 3: the sum of the ``q`` smallest per-member
    response floors.  Pure arithmetic on the declared floors; never consults an
    execution.

``execution_floor``
    Computed in :mod:`ptr_exp.evidence` from one execution's allocation witness.

``catalog_certificate``
    The minimum of the ledger-derived execution floors over an explicitly
    enumerated route catalog.

``observed_minimum``
    The minimum realized named-buyer net outflow over the same catalog.

The experiment asserts that all four agree; nothing in the code makes them agree
by construction.
"""

from __future__ import annotations

from itertools import combinations
from math import inf
from typing import Iterable, Sequence


def theory_cover(prices: Sequence[int], threshold: int) -> int:
    if not 1 <= threshold <= len(prices):
        raise ValueError("invalid threshold")
    if any(price < 0 for price in prices):
        raise ValueError("negative price")
    return sum(sorted(prices)[:threshold])


def uniform_positive_count(prices: Sequence[int], threshold: int) -> bool:
    return sum(1 for price in prices if price > 0) > len(prices) - threshold


def catalog_certificate(route_floors: Iterable[int | None]) -> int:
    """Return the minimum floor of a *complete* materialized route catalog.

    ``None`` is not a cheap route. It means that the corresponding route did
    not produce a ledger-derived certificate. Silently dropping it would turn
    an incomplete catalog into a numeric certificate, which is precisely the
    fail-open behavior the experiment is intended to exclude.
    """

    values = list(route_floors)
    if not values:
        raise ValueError("empty route catalog")
    if any(value is None for value in values):
        raise ValueError("incomplete route catalog: at least one route has no certified floor")
    return min(int(value) for value in values)


def brute_force_weighted(weights: Sequence[int], prices: Sequence[int], threshold: int) -> tuple[int, tuple[int, ...]]:
    if len(weights) != len(prices):
        raise ValueError("length mismatch")
    best = inf
    best_set: tuple[int, ...] = ()
    n = len(weights)
    for size in range(1, n + 1):
        for coalition in combinations(range(n), size):
            if sum(weights[i] for i in coalition) >= threshold:
                cost = sum(prices[i] for i in coalition)
                if cost < best:
                    best = cost
                    best_set = tuple(i + 1 for i in coalition)
    if best is inf:
        raise ValueError("threshold unreachable")
    return int(best), best_set


def weighted_dp(weights: Sequence[int], prices: Sequence[int], threshold: int) -> int:
    if len(weights) != len(prices):
        raise ValueError("length mismatch")
    if threshold <= 0:
        return 0
    dp: list[int | None] = [None] * (threshold + 1)
    dp[0] = 0
    for weight, price in zip(weights, prices):
        if weight <= 0 or price < 0:
            raise ValueError("invalid weight/price")
        next_dp = dp.copy()
        for accumulated, cost in enumerate(dp):
            if cost is None:
                continue
            target = min(threshold, accumulated + weight)
            candidate = cost + price
            if next_dp[target] is None or candidate < next_dp[target]:
                next_dp[target] = candidate
        dp = next_dp
    if dp[threshold] is None:
        raise ValueError("threshold unreachable")
    return dp[threshold]
