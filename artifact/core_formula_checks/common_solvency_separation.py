#!/usr/bin/env python3
"""Exhaustive fixed-uniform-cost common-solvency separation check."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import inf


def powerset(items: tuple[str, ...]):
    for size in range(len(items) + 1):
        yield from combinations(items, size)


def collateral(
    acquired: frozenset[str],
    seeds: frozenset[str],
    cores: frozenset[str],
    liquidity: Fraction,
) -> Fraction:
    c = liquidity + 1
    j = len(acquired & seeds)
    r = len(acquired & cores)
    return (
        j * c
        + Fraction(c - liquidity, len(seeds)) * j * r
        + ((2 * c - liquidity) if r == 2 else 0)
    )


def check_instance(k: int, liquidity: Fraction) -> tuple[Fraction, Fraction]:
    delta = Fraction(1, 4)
    threshold = 1 - delta
    seed_names = tuple(f"s{index}" for index in range(k))
    core_names = ("a", "b")
    members = seed_names + core_names
    seeds = frozenset(seed_names)
    cores = frozenset(core_names)
    c = liquidity + 1
    weights = {
        **{seed: delta / k for seed in seed_names},
        "a": (1 - delta) / 2,
        "b": (1 - delta) / 2,
    }
    costs = {member: c for member in members}
    subsets = [frozenset(raw) for raw in powerset(members)]

    if collateral(frozenset(), seeds, cores, liquidity) != 0:
        raise SystemExit("UNIFORM_COLLATERAL_NORMALIZATION=FAIL")
    for left in subsets:
        left_value = collateral(left, seeds, cores, liquidity)
        if left_value < 0:
            raise SystemExit("UNIFORM_COLLATERAL_NONNEGATIVITY=FAIL")
        for right in subsets:
            right_value = collateral(right, seeds, cores, liquidity)
            if left <= right and left_value > right_value:
                raise SystemExit(
                    f"UNIFORM_COLLATERAL_MONOTONICITY=FAIL k={k} liquidity={liquidity}"
                )
            union = collateral(left | right, seeds, cores, liquidity)
            intersection = collateral(left & right, seeds, cores, liquidity)
            if left_value + right_value > union + intersection:
                raise SystemExit(
                    f"UNIFORM_COLLATERAL_SUPERMODULARITY=FAIL k={k} liquidity={liquidity}"
                )

    def exposure(acquired: frozenset[str]) -> Fraction:
        return sum((weights[member] for member in acquired), Fraction())

    best: dict[frozenset[str], Fraction] = {frozenset(): Fraction()}
    frontier = [frozenset()]
    while frontier:
        acquired = frontier.pop()
        payment = best[acquired]
        if exposure(acquired) >= threshold:
            continue
        for member in members:
            if member in acquired:
                continue
            next_set = acquired | {member}
            next_payment = payment + costs[member]
            if next_payment > liquidity + collateral(
                next_set, seeds, cores, liquidity
            ):
                continue
            if next_payment < best.get(next_set, inf):
                best[next_set] = next_payment
                frontier.append(next_set)

    for size in range(k + 1):
        seed_state = frozenset(seed_names[:size])
        if seed_state not in best or best[seed_state] != size * c:
            raise SystemExit(
                f"UNIFORM_SEED_PATH=FAIL k={k} liquidity={liquidity} size={size}"
            )
        if size < k:
            for core in cores:
                candidate = seed_state | {core}
                if candidate in best:
                    raise SystemExit(
                        f"UNIFORM_CORE_PREREQUISITE=FAIL k={k} "
                        f"liquidity={liquidity} size={size}"
                    )

    sequential = min(
        payment
        for acquired, payment in best.items()
        if exposure(acquired) >= threshold
    )
    package = min(
        sum((costs[member] for member in subset), Fraction())
        for subset in subsets
        if exposure(subset) >= threshold
        and sum((costs[member] for member in subset), Fraction())
        <= liquidity + collateral(subset, seeds, cores, liquidity)
    )
    return sequential, package


for liquidity in (
    Fraction(),
    Fraction(1, 2),
    Fraction(1),
    Fraction(5),
    Fraction(100),
):
    for k in (1, 2, 3, 5, 8):
        sequential, package = check_instance(k, liquidity)
        c = liquidity + 1
        expected = ((k + 2) * c, 2 * c)
        if (sequential, package) != expected:
            raise SystemExit(
                "FIXED_UNIFORM_COST_SEPARATION=FAIL "
                f"k={k} liquidity={liquidity} "
                f"got={(sequential, package)} expected={expected}"
            )
        print(
            "FIXED_UNIFORM_COST_INSTANCE=PASS "
            f"liquidity={liquidity} k={k} common_cost={c} "
            f"sequential={sequential} package={package} "
            f"gap={sequential-package} ratio={sequential/package}"
        )

print("UNIFORM_COLLATERAL_NORMALIZATION=PASS")
print("UNIFORM_COLLATERAL_NONNEGATIVITY=PASS")
print("UNIFORM_COLLATERAL_MONOTONICITY=PASS")
print("UNIFORM_COLLATERAL_SUPERMODULARITY=PASS")
print("UNIFORM_SEED_PATH=PASS")
print("UNIFORM_CORE_PREREQUISITE=PASS")
print("FIXED_UNIFORM_COST_SEPARATION=PASS")