#!/usr/bin/env python3
"""Exact utilities for certified-defense lattice and Möbius experiments.

The module deliberately uses only the Python standard library.  Fractions are
used for the theorem construction so that zero higher-order coefficients are
checked exactly rather than through floating-point tolerances.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import inf
from typing import Callable, Iterable, Sequence


Number = int | float | Fraction


def sequential_float_sum(values: Iterable[float]) -> float:
    """Sum floats in a fixed left-to-right order across Python versions.

    CPython 3.12 changed the implementation of the built-in ``sum`` for
    floating-point inputs.  The recorded artifact was produced with Python
    3.11, so spelling out the accumulation order keeps regenerated CSV bytes
    identical on both 3.11 and 3.12.
    """

    total = 0.0
    for value in values:
        total += value
    return total


@dataclass(frozen=True)
class StepCap:
    """Right-continuous, weakly increasing acquisition-cap schedule."""

    breakpoints: tuple[tuple[Fraction, Fraction], ...]

    def __post_init__(self) -> None:
        if not self.breakpoints or self.breakpoints[0][0] != 0:
            raise ValueError("a cap schedule must start at exposure zero")
        previous_alpha = Fraction(-1)
        previous_value = Fraction(-1)
        for alpha, value in self.breakpoints:
            if alpha <= previous_alpha:
                raise ValueError("cap breakpoints must be strictly increasing")
            if value < previous_value:
                raise ValueError("cap values must be weakly increasing")
            previous_alpha = alpha
            previous_value = value

    def at(self, exposure: Fraction) -> Fraction:
        value = self.breakpoints[0][1]
        for alpha, candidate in self.breakpoints[1:]:
            if exposure < alpha:
                break
            value = candidate
        return value


@dataclass(frozen=True)
class SequentialInstance:
    weights: tuple[Fraction, ...]
    resistances: tuple[Fraction, ...]
    caps: tuple[StepCap, ...]
    threshold: Fraction
    initial_exposure: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        n = len(self.weights)
        if len(self.resistances) != n or len(self.caps) != n:
            raise ValueError("weights, resistances, and caps must have equal length")
        if any(weight <= 0 for weight in self.weights):
            raise ValueError("member weights must be positive")
        if sum(self.weights) != 1:
            raise ValueError("member weights must sum to one")
        if not (0 <= self.initial_exposure < self.threshold <= 1):
            raise ValueError("invalid exposure or threshold")


@dataclass(frozen=True)
class SequentialSolution:
    """Exact minimum-cost threshold-reaching set and one acquisition witness."""

    cost: Fraction
    member_mask: int
    witness: tuple[int, ...]


def exact_minimum_sequential_solution(
    instance: SequentialInstance,
) -> SequentialSolution | None:
    """Return the exact minimum solution, or ``None`` when none is feasible.

    Masks and candidate members are visited in increasing integer order.  Ties
    therefore have a stable witness, which is useful for byte-reproducible
    experiment records without changing the certificate value.
    """

    n = len(instance.weights)
    size = 1 << n
    weight_sum = [Fraction(0)] * size
    resistance_sum = [Fraction(0)] * size
    for mask in range(1, size):
        bit = mask & -mask
        member = bit.bit_length() - 1
        previous = mask ^ bit
        weight_sum[mask] = weight_sum[previous] + instance.weights[member]
        resistance_sum[mask] = resistance_sum[previous] + instance.resistances[member]

    reachable = bytearray(size)
    reachable[0] = 1
    predecessor: list[tuple[int, int] | None] = [None] * size
    best_mask: int | None = None
    best_cost: Fraction | None = None
    full_mask = size - 1

    for mask in range(size):
        if not reachable[mask]:
            continue
        exposure = instance.initial_exposure + weight_sum[mask]
        if exposure >= instance.threshold:
            cost = resistance_sum[mask]
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_mask = mask
            continue

        remaining = full_mask ^ mask
        while remaining:
            bit = remaining & -remaining
            member = bit.bit_length() - 1
            if instance.resistances[member] <= instance.caps[member].at(exposure):
                next_mask = mask | bit
                if not reachable[next_mask]:
                    reachable[next_mask] = 1
                    predecessor[next_mask] = (mask, member)
            remaining ^= bit

    if best_mask is None or best_cost is None:
        return None

    reversed_witness: list[int] = []
    cursor = best_mask
    while cursor:
        step = predecessor[cursor]
        if step is None:
            raise AssertionError("reachable mask is missing a predecessor")
        cursor, member = step
        reversed_witness.append(member)
    reversed_witness.reverse()
    return SequentialSolution(
        cost=best_cost,
        member_mask=best_mask,
        witness=tuple(reversed_witness),
    )


def exact_minimum_sequential_cost(instance: SequentialInstance) -> Fraction | None:
    """Return the exact minimum cost, or None when no attack is feasible."""

    solution = exact_minimum_sequential_solution(instance)
    return None if solution is None else solution.cost


def coordinated_defense_instance(
    k: int, multiple: int | Fraction, action_mask: int
) -> SequentialInstance:
    """Instantiate the coordinated-defense construction behind Theorem 5.12."""

    if k < 1:
        raise ValueError("k must be positive")
    multiple = Fraction(multiple)
    if multiple <= 1:
        raise ValueError("multiple must exceed one")

    threshold = Fraction(1, 3)
    delta = Fraction(1, 6 * k)
    entry_weight = delta
    terminal_weight = threshold - delta
    fallback_weight = threshold
    filler_weight = 1 - k * entry_weight - terminal_weight - fallback_weight

    entry_cap = StepCap(((Fraction(0), Fraction(1)),))
    terminal_cap = StepCap(
        ((Fraction(0), Fraction(0)), (delta, Fraction(1)))
    )
    fallback_cap = StepCap(((Fraction(0), 2 * multiple),))
    filler_cap = StepCap(((Fraction(0), Fraction(0)),))

    weights = [entry_weight] * k + [terminal_weight, fallback_weight, filler_weight]
    resistances = []
    for member in range(k):
        protected = bool(action_mask & (1 << member))
        resistances.append(2 * multiple + 1 if protected else Fraction(1))
    resistances.extend((Fraction(1), 2 * multiple, 2 * multiple + 1))
    caps = [entry_cap] * k + [terminal_cap, fallback_cap, filler_cap]

    return SequentialInstance(
        weights=tuple(weights),
        resistances=tuple(resistances),
        caps=tuple(caps),
        threshold=threshold,
    )


def coordinated_defense_values(k: int, multiple: int | Fraction) -> list[Fraction]:
    values: list[Fraction] = []
    for action_mask in range(1 << k):
        value = exact_minimum_sequential_cost(
            coordinated_defense_instance(k, multiple, action_mask)
        )
        if value is None:
            raise AssertionError("the fallback attack should always be feasible")
        values.append(value)
    return values


def mobius_transform(values: Sequence[Number], k: int) -> list[Number]:
    """Fast subset Möbius transform on the Boolean lattice."""

    if len(values) != 1 << k:
        raise ValueError("values must contain one entry for every subset")
    coefficients = list(values)
    for bit_index in range(k):
        bit = 1 << bit_index
        for mask in range(1 << k):
            if mask & bit:
                coefficients[mask] -= coefficients[mask ^ bit]
    return coefficients


def zeta_transform(coefficients: Sequence[Number], k: int) -> list[Number]:
    """Inverse of mobius_transform."""

    if len(coefficients) != 1 << k:
        raise ValueError("coefficients must contain one entry for every subset")
    values = list(coefficients)
    for bit_index in range(k):
        bit = 1 << bit_index
        for mask in range(1 << k):
            if mask & bit:
                values[mask] += values[mask ^ bit]
    return values


def truncated_value(
    coefficients: Sequence[Number], k: int, mask: int, max_order: int
) -> Number:
    if len(coefficients) != 1 << k:
        raise ValueError("coefficients must contain one entry for every subset")
    total: Number = 0
    subset = mask
    while True:
        if subset.bit_count() <= max_order:
            total += coefficients[subset]
        if subset == 0:
            break
        subset = (subset - 1) & mask
    return total


def is_monotone(values: Sequence[Number], k: int, tolerance: float = 0.0) -> bool:
    if len(values) != 1 << k:
        raise ValueError("values must contain one entry for every subset")
    for mask, value in enumerate(values):
        remaining = ((1 << k) - 1) ^ mask
        while remaining:
            bit = remaining & -remaining
            if float(values[mask | bit]) + tolerance < float(value):
                return False
            remaining ^= bit
    return True


def minimal_target_masks(
    values: Sequence[Number], k: int, target: Number, tolerance: float = 1e-12
) -> list[int]:
    """Return inclusion-minimal subsets whose value reaches target."""

    if not is_monotone(values, k, tolerance):
        raise ValueError("minimal target masks require a monotone set function")
    minimal: list[int] = []
    for mask, value in enumerate(values):
        if float(value) + tolerance < float(target):
            continue
        is_minimal = True
        present = mask
        while present:
            bit = present & -present
            if float(values[mask ^ bit]) + tolerance >= float(target):
                is_minimal = False
                break
            present ^= bit
        if is_minimal:
            minimal.append(mask)
    return minimal


def uniform_threshold_certificate(
    resistances: Sequence[float], increments: Sequence[float], action_mask: int, q: int
) -> float:
    if len(resistances) != len(increments):
        raise ValueError("resistance and increment vectors must have equal length")
    if not (1 <= q <= len(resistances)):
        raise ValueError("q must be between one and the committee size")
    post = [
        resistance + (increments[i] if action_mask & (1 << i) else 0.0)
        for i, resistance in enumerate(resistances)
    ]
    return sequential_float_sum(sorted(post)[:q])


def exact_budget_maximizer(
    value: Callable[[int], float], action_count: int, budget: int
) -> tuple[int, float]:
    best_mask = 0
    best_value = value(0)
    for chosen in combinations(range(action_count), budget):
        mask = sum(1 << action for action in chosen)
        candidate = value(mask)
        if candidate > best_value:
            best_mask = mask
            best_value = candidate
    return best_mask, best_value


def marginal_greedy(
    value: Callable[[int], float], action_count: int, budget: int
) -> tuple[int, float]:
    mask = 0
    current = value(mask)
    for _ in range(budget):
        candidates = []
        for action in range(action_count):
            bit = 1 << action
            if mask & bit:
                continue
            candidate_value = value(mask | bit)
            candidates.append((candidate_value - current, -action, bit, candidate_value))
        if not candidates:
            break
        _, _, bit, current = max(candidates)
        mask |= bit
    return mask, current


def decoy_fixed_family_value(
    k: int, multiple: float, epsilon: float
) -> tuple[int, Callable[[int], float]]:
    """Return a fixed-family instance in which singleton-greedy selects decoys.

    Actions 0..k-1 raise one distinct cheap cover.  Actions k..2k-1 raise every
    cheap cover by epsilon.  The fallback cover has cost 2*multiple.
    """

    if k < 2 or multiple <= 1 or epsilon <= 0:
        raise ValueError("invalid decoy construction parameters")
    blocking_increment = 2.0 * multiple
    action_count = 2 * k

    def value(mask: int) -> float:
        cheap_costs = []
        decoy_count = sum(bool(mask & (1 << action)) for action in range(k, 2 * k))
        common_increment = epsilon * decoy_count
        for path in range(k):
            path_increment = blocking_increment if mask & (1 << path) else 0.0
            cheap_costs.append(2.0 + common_increment + path_increment)
        return min([2.0 * multiple, *cheap_costs])

    return action_count, value
