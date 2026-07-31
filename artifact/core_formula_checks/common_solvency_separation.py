#!/usr/bin/env python3
"""Finite-state check of liquidity-robust common-solvency separation."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import inf


def powerset(items: tuple[str, ...]):
    for size in range(len(items) + 1):
        yield from combinations(items, size)


def floor_cost(
    acquired: frozenset[str],
    seeds: frozenset[str],
    cores: frozenset[str],
    liquidity: Fraction,
) -> Fraction:
    c = liquidity + 1
    q = liquidity + 2
    return c * len(acquired & seeds) + q * len(acquired & cores)


def collateral(
    acquired: frozenset[str],
    seeds: frozenset[str],
    cores: frozenset[str],
    liquidity: Fraction,
) -> Fraction:
    c = liquidity + 1
    if seeds <= acquired or cores <= acquired:
        return floor_cost(acquired, seeds, cores, liquidity) - liquidity
    if len(acquired & cores) == 1:
        return c * len(acquired & seeds)
    return max(c * len(acquired & seeds) - liquidity, Fraction())


def check_instance(k: int, liquidity: Fraction) -> tuple[Fraction, Fraction]:
    delta = Fraction(1, 4)
    threshold = 1 - delta
    seed_names = tuple(f"s{index}" for index in range(k))
    core_names = ("a", "b")
    members = seed_names + core_names
    seeds = frozenset(seed_names)
    cores = frozenset(core_names)
    c = liquidity + 1
    q = liquidity + 2
    weights = {
        **{seed: delta / k for seed in seed_names},
        "a": (1 - delta) / 2,
        "b": (1 - delta) / 2,
    }
    costs = {**{seed: c for seed in seed_names}, "a": q, "b": q}

    all_subsets = [
        frozenset(raw_subset) for raw_subset in powerset(members)
    ]
    if collateral(frozenset(), seeds, cores, liquidity) != 0:
        raise SystemExit(
            "LIQUIDITY_COLLATERAL_NORMALIZATION=FAIL "
            f"k={k} liquidity={liquidity}"
        )
    for left in all_subsets:
        left_value = collateral(left, seeds, cores, liquidity)
        if left_value < 0:
            raise SystemExit(
                "LIQUIDITY_COLLATERAL_NONNEGATIVITY=FAIL "
                f"k={k} liquidity={liquidity} set={sorted(left)}"
            )
        for right in all_subsets:
            if left <= right and left_value > collateral(
                right, seeds, cores, liquidity
            ):
                raise SystemExit(
                    "LIQUIDITY_COLLATERAL_MONOTONICITY=FAIL "
                    f"k={k} liquidity={liquidity} "
                    f"left={sorted(left)} right={sorted(right)}"
                )

    best: dict[frozenset[str], Fraction] = {frozenset(): Fraction()}
    frontier = [frozenset()]
    while frontier:
        acquired = frontier.pop()
        payment = best[acquired]
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

    # Every nonempty reachable checkpoint has zero slack. Hence an alternative
    # overpayment history cannot create a second cap at the same exposure.
    for acquired, payment in best.items():
        if acquired:
            expected = floor_cost(acquired, seeds, cores, liquidity)
            budget = liquidity + collateral(acquired, seeds, cores, liquidity)
            if payment != expected or budget != expected:
                raise SystemExit(
                    "LIQUIDITY_CHECKPOINT_EXACTNESS=FAIL "
                    f"k={k} liquidity={liquidity} set={sorted(acquired)} "
                    f"payment={payment} floor={expected} budget={budget}"
                )

    def exposure(acquired: frozenset[str]) -> Fraction:
        return sum((weights[member] for member in acquired), Fraction())

    def offer_cap(acquired: frozenset[str], member: str) -> Fraction:
        if member in acquired:
            raise ValueError("offer cap requested for an acquired member")
        next_set = acquired | {member}
        return (
            liquidity
            + collateral(next_set, seeds, cores, liquidity)
            - best[acquired]
        )

    def available(acquired: frozenset[str], member: str) -> bool:
        if member in acquired:
            return False
        return costs[member] <= offer_cap(acquired, member)

    preterminal = [state for state in best if exposure(state) < threshold]
    # Reachable exposure is a sufficient state for the actual maximum offer
    # cap, not merely for the yes/no predicate at the member's floor.
    for left in preterminal:
        for right in preterminal:
            if exposure(left) != exposure(right):
                continue
            for member in members:
                if member not in left and member not in right:
                    if offer_cap(left, member) != offer_cap(right, member):
                        raise SystemExit(
                            "LIQUIDITY_CAP_EXPOSURE_SUFFICIENCY=FAIL "
                            f"k={k} liquidity={liquidity} member={member} "
                            f"left={offer_cap(left, member)} "
                            f"right={offer_cap(right, member)}"
                        )

    # Check the displayed closed form and weak monotonicity of the cap itself.
    for member in members:
        states = sorted(
            (state for state in preterminal if member not in state),
            key=exposure,
        )
        previous_cap = None
        for state in states:
            cap = offer_cap(state, member)
            expected_cap = (
                c
                if member in seeds
                else liquidity if exposure(state) < delta else q
            )
            if cap != expected_cap:
                raise SystemExit(
                    "LIQUIDITY_CAP_FORMULA=FAIL "
                    f"k={k} liquidity={liquidity} member={member} "
                    f"state={sorted(state)} cap={cap} expected={expected_cap}"
                )
            if previous_cap is not None and cap < previous_cap:
                raise SystemExit(
                    "LIQUIDITY_CAP_MONOTONICITY=FAIL "
                    f"k={k} liquidity={liquidity} member={member} "
                    f"previous={previous_cap} cap={cap}"
                )
            previous_cap = cap

    sequential = min(
        payment
        for acquired, payment in best.items()
        if exposure(acquired) >= threshold
    )
    package = min(
        sum((costs[member] for member in subset), Fraction())
        for raw_subset in powerset(members)
        for subset in [frozenset(raw_subset)]
        if exposure(subset) >= threshold
        and sum((costs[member] for member in subset), Fraction())
        <= liquidity + collateral(subset, seeds, cores, liquidity)
    )
    return sequential, package


for liquidity in (Fraction(), Fraction(1, 2), Fraction(1), Fraction(5), Fraction(100)):
    for k in (1, 2, 3, 5, 8):
        sequential, package = check_instance(k, liquidity)
        c = liquidity + 1
        q = liquidity + 2
        expected = (k * c + 2 * q, 2 * q)
        if (sequential, package) != expected:
            raise SystemExit(
                "LIQUIDITY_ROBUST_SEPARATION=FAIL "
                f"k={k} liquidity={liquidity} "
                f"got={(sequential, package)} expected={expected}"
            )
        print(
            "LIQUIDITY_ROBUST_INSTANCE=PASS "
            f"liquidity={liquidity} k={k} "
            f"sequential={sequential} package={package} gap={sequential-package}"
        )

# Regression test: the superseded two-branch collateral formula proves only
# binary unavailability. At positive liquidity its actual core offer cap falls
# after the first seed, so it must be rejected as a canonical monotone cap.
legacy_liquidity = Fraction(1)
legacy_k = 2
legacy_c = legacy_liquidity + 1
legacy_seeds = frozenset(("s0", "s1"))
legacy_cores = frozenset(("a", "b"))


def legacy_collateral(acquired: frozenset[str]) -> Fraction:
    if legacy_seeds <= acquired or legacy_cores <= acquired:
        return floor_cost(
            acquired, legacy_seeds, legacy_cores, legacy_liquidity
        ) - legacy_liquidity
    return max(
        legacy_c * len(acquired & legacy_seeds) - legacy_liquidity,
        Fraction(),
    )


legacy_empty = frozenset()
legacy_one_seed = frozenset(("s0",))
legacy_cap_empty = (
    legacy_liquidity + legacy_collateral(frozenset(("a",)))
)
legacy_cap_after_seed = (
    legacy_liquidity
    + legacy_collateral(legacy_one_seed | {"a"})
    - floor_cost(
        legacy_one_seed, legacy_seeds, legacy_cores, legacy_liquidity
    )
)
if not legacy_cap_after_seed < legacy_cap_empty:
    raise SystemExit("OLD_COLLATERAL_CAP_MONOTONICITY=NOT_REJECTED")

print("OLD_COLLATERAL_CAP_MONOTONICITY=REJECTED")
print("LIQUIDITY_COLLATERAL_NORMALIZATION=PASS")
print("LIQUIDITY_COLLATERAL_NONNEGATIVITY=PASS")
print("LIQUIDITY_COLLATERAL_MONOTONICITY=PASS")
print("LIQUIDITY_CHECKPOINT_EXACTNESS=PASS")
print("LIQUIDITY_CAP_EXPOSURE_SUFFICIENCY=PASS")
print("LIQUIDITY_CAP_FORMULA=PASS")
print("LIQUIDITY_CAP_MONOTONICITY=PASS")
print("LIQUIDITY_ROBUST_SEPARATION=PASS")