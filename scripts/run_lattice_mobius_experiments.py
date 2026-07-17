#!/usr/bin/env python3
"""Run deterministic lattice, Möbius, and remediation experiments."""
from __future__ import annotations

import csv
import random
import statistics
from pathlib import Path

from defense_lattice import (
    coordinated_defense_values,
    decoy_fixed_family_value,
    exact_budget_maximizer,
    is_monotone,
    marginal_greedy,
    minimal_target_masks,
    mobius_transform,
    truncated_value,
    uniform_threshold_certificate,
    zeta_transform,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
RANDOM_TRIALS = 100
RANDOM_SEED = 20260714


def write_rows(path: Path, header: list[str], rows: list[tuple[object, ...]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def pure_kway_experiments() -> tuple[int, int]:
    summary_rows: list[tuple[object, ...]] = []
    truncation_rows: list[tuple[object, ...]] = []
    cases = 0
    passed = 0

    for k in [2, 3, 4, 5, 6, 8]:
        for multiple in [2, 10, 100]:
            values = coordinated_defense_values(k, multiple)
            coefficients = mobius_transform(values, k)
            reconstructed = zeta_transform(coefficients, k)
            full_mask = (1 << k) - 1
            proper_nonempty = coefficients[1:full_mask]
            max_proper = max((abs(value) for value in proper_nonempty), default=0)
            top = coefficients[full_mask]
            theorem_pass = (
                reconstructed == values
                and is_monotone(values, k)
                and values[0] == 2
                and values[full_mask] == 2 * multiple
                and max_proper == 0
                and top == 2 * multiple - 2
            )
            cases += 1
            passed += int(theorem_pass)
            summary_rows.append(
                (
                    k,
                    multiple,
                    values[0],
                    values[full_mask],
                    top,
                    max_proper,
                    theorem_pass,
                )
            )

            for max_order in range(1, k):
                approximate = truncated_value(coefficients, k, full_mask, max_order)
                ratio = float(values[full_mask] / approximate)
                truncation_rows.append(
                    (
                        k,
                        multiple,
                        max_order,
                        values[full_mask],
                        approximate,
                        ratio,
                    )
                )

    write_rows(
        RESULTS / "mobius_pure_kway.csv",
        [
            "k",
            "multiple_M",
            "baseline",
            "full_value",
            "full_order_coefficient",
            "max_abs_nonempty_proper_coefficient",
            "theorem_check",
        ],
        summary_rows,
    )
    write_rows(
        RESULTS / "mobius_truncation.csv",
        [
            "k",
            "multiple_M",
            "maximum_retained_order",
            "true_full_value",
            "truncated_full_value",
            "underprediction_ratio",
        ],
        truncation_rows,
    )
    return cases, passed


def random_uniform_experiments() -> tuple[int, int]:
    rng = random.Random(RANDOM_SEED)
    interaction_rows: list[tuple[object, ...]] = []
    truncation_rows: list[tuple[object, ...]] = []
    target_rows: list[tuple[object, ...]] = []
    algorithm_rows: list[tuple[object, ...]] = []
    monotonicity_failures = 0

    n = 7
    q = 4
    for trial in range(RANDOM_TRIALS):
        resistances = [1.0 + 9.0 * rng.random() for _ in range(n)]
        increments = [0.5 + 12.0 * rng.random() for _ in range(n)]
        values = [
            uniform_threshold_certificate(resistances, increments, mask, q)
            for mask in range(1 << n)
        ]
        if not is_monotone(values, n, tolerance=1e-10):
            monotonicity_failures += 1

        coefficients = mobius_transform(values, n)
        scale = max(1.0, values[-1] - values[0])
        for order in range(1, n + 1):
            mass = sum(
                abs(coefficient)
                for mask, coefficient in enumerate(coefficients)
                if mask.bit_count() == order
            )
            interaction_rows.append((trial, order, mass, mass / scale))

        for max_order in [1, 2, 3]:
            absolute_errors = []
            relative_errors = []
            for mask, true_value in enumerate(values):
                approximate = float(truncated_value(coefficients, n, mask, max_order))
                error = abs(true_value - approximate)
                absolute_errors.append(error)
                relative_errors.append(error / max(1.0, abs(true_value)))
            truncation_rows.append(
                (
                    trial,
                    max_order,
                    max(absolute_errors),
                    statistics.mean(absolute_errors),
                    max(relative_errors),
                )
            )

        target = values[0] + 0.6 * (values[-1] - values[0])
        minimal = minimal_target_masks(values, n, target)
        target_rows.append(
            (
                trial,
                values[0],
                values[-1],
                target,
                len(minimal),
                min((mask.bit_count() for mask in minimal), default=""),
            )
        )

        value = lambda mask: uniform_threshold_certificate(  # noqa: E731
            resistances, increments, mask, q
        )
        for budget in [1, 2, 3]:
            _, exact_value = exact_budget_maximizer(value, n, budget)
            _, greedy_value = marginal_greedy(value, n, budget)
            gain_denominator = max(1e-12, exact_value - values[0])
            gain_ratio = (greedy_value - values[0]) / gain_denominator
            algorithm_rows.append(
                (trial, budget, values[0], exact_value, greedy_value, gain_ratio)
            )

    write_rows(
        RESULTS / "mobius_random_order_mass.csv",
        ["trial", "order", "absolute_interaction_mass", "normalized_mass"],
        interaction_rows,
    )
    write_rows(
        RESULTS / "mobius_random_truncation.csv",
        [
            "trial",
            "maximum_retained_order",
            "maximum_absolute_error",
            "mean_absolute_error",
            "maximum_relative_error",
        ],
        truncation_rows,
    )
    write_rows(
        RESULTS / "lattice_target_summary.csv",
        [
            "trial",
            "baseline",
            "full_defense_value",
            "target",
            "minimal_plan_count",
            "minimum_plan_size",
        ],
        target_rows,
    )
    write_rows(
        RESULTS / "uniform_allocation_algorithms.csv",
        [
            "trial",
            "action_budget",
            "baseline",
            "exact_value",
            "greedy_value",
            "greedy_gain_ratio",
        ],
        algorithm_rows,
    )
    return RANDOM_TRIALS, monotonicity_failures


def decoy_greedy_experiments() -> tuple[int, int]:
    rows: list[tuple[object, ...]] = []
    cases = 0
    passed = 0
    for k in [2, 3, 4, 6, 8]:
        for multiple in [10.0, 100.0, 1000.0]:
            epsilon = 1.0 / (10.0 * k)
            action_count, value = decoy_fixed_family_value(k, multiple, epsilon)
            exact_mask, exact_value = exact_budget_maximizer(value, action_count, k)
            greedy_mask, greedy_value = marginal_greedy(value, action_count, k)
            exact_gain = exact_value - value(0)
            greedy_gain = greedy_value - value(0)
            gain_ratio = greedy_gain / exact_gain
            case_pass = exact_mask == (1 << k) - 1 and greedy_mask >> k == (1 << k) - 1
            cases += 1
            passed += int(case_pass)
            rows.append(
                (
                    k,
                    multiple,
                    epsilon,
                    exact_value,
                    greedy_value,
                    gain_ratio,
                    case_pass,
                )
            )
    write_rows(
        RESULTS / "greedy_decoy_failure.csv",
        [
            "k",
            "multiple_M",
            "decoy_increment",
            "exact_value",
            "greedy_value",
            "greedy_to_exact_gain_ratio",
            "construction_check",
        ],
        rows,
    )
    return cases, passed


def main() -> None:
    pure_cases, pure_passed = pure_kway_experiments()
    random_trials, monotonicity_failures = random_uniform_experiments()
    decoy_cases, decoy_passed = decoy_greedy_experiments()
    print(f"pure_kway_cases={pure_cases}")
    print(f"pure_kway_passed={pure_passed}")
    print(f"random_uniform_trials={random_trials}")
    print(f"random_monotonicity_failures={monotonicity_failures}")
    print(f"decoy_greedy_cases={decoy_cases}")
    print(f"decoy_greedy_passed={decoy_passed}")
    print(f"random_seed={RANDOM_SEED}")


if __name__ == "__main__":
    main()
