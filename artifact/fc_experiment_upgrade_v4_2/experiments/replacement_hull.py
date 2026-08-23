from __future__ import annotations

import argparse
import math
import time
from collections import defaultdict

import numpy as np
from scipy.optimize import linprog

from common import RESULTS, ensure_results, write_csv, write_json


DEFAULT_SEEDS = (20260725, 20260726, 20260727, 20260728, 20260729)


def l1_distance_to_hull(target: np.ndarray, alternatives: np.ndarray):
    alternatives = np.asarray(alternatives, dtype=float)
    target = np.asarray(target, dtype=float)
    k, dimension = alternatives.shape
    # Variables are lambda_1..lambda_k and residual magnitudes u_1..u_d.
    c = np.r_[np.zeros(k), np.ones(dimension)]
    a_ub = []
    b_ub = []
    for coordinate in range(dimension):
        row = np.zeros(k + dimension)
        row[:k] = alternatives[:, coordinate]
        row[k + coordinate] = -1
        a_ub.append(row)
        b_ub.append(target[coordinate])

        row = np.zeros(k + dimension)
        row[:k] = -alternatives[:, coordinate]
        row[k + coordinate] = -1
        a_ub.append(row)
        b_ub.append(-target[coordinate])

    a_eq = np.zeros((1, k + dimension))
    a_eq[0, :k] = 1
    result = linprog(
        c,
        A_ub=np.asarray(a_ub),
        b_ub=np.asarray(b_ub),
        A_eq=a_eq,
        b_eq=np.array([1.0]),
        bounds=[(0, None)] * (k + dimension),
        method="highs",
        options={
            "primal_feasibility_tolerance": 1e-10,
            "dual_feasibility_tolerance": 1e-10,
            "ipm_optimality_tolerance": 1e-12,
        },
    )
    if not result.success:
        raise RuntimeError(result.message)
    return float(result.fun), result.x[:k]


def simplex_points(rng: np.random.Generator, count: int, dimension: int):
    points = rng.dirichlet(np.ones(dimension), size=count) + 0.01
    return points / points.sum(axis=1, keepdims=True)


def parse_seeds(raw: str) -> tuple[int, ...]:
    seeds = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    if len(set(seeds)) != len(seeds):
        raise argparse.ArgumentTypeError("seeds must be distinct")
    return seeds


def wilson_upper(errors: int, trials: int, z: float = 1.959963984540054) -> float:
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= errors <= trials:
        raise ValueError("errors must lie between zero and trials")
    rate = errors / trials
    denominator = 1 + z * z / trials
    center = rate + z * z / (2 * trials)
    radius = z * math.sqrt(
        rate * (1 - rate) / trials + z * z / (4 * trials * trials)
    )
    return (center + radius) / denominator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=60)
    parser.add_argument(
        "--seeds",
        type=parse_seeds,
        default=DEFAULT_SEEDS,
        help="comma-separated deterministic seeds",
    )
    parser.add_argument("--tolerance", type=float, default=1e-8)
    args = parser.parse_args()

    rows = []
    tolerance_rows = []
    labels = ("replaceable", "separable", "near_boundary")
    scales = ((3, 4), (5, 5), (10, 8), (20, 12))
    trial = 0
    for seed in args.seeds:
        rng = np.random.default_rng(seed)
        for dimension, alternative_count in scales:
            for label in labels:
                for repetition in range(args.repetitions):
                    alternatives = simplex_points(
                        rng, count=alternative_count, dimension=dimension
                    )
                    coefficients = rng.dirichlet(np.ones(alternative_count))
                    hull_point = coefficients @ alternatives
                    epsilon = 0.0
                    construction_residual = None
                    analytic_margin = None
                    if label == "replaceable":
                        target = hull_point
                        construction_residual = float(
                            np.abs(coefficients @ alternatives - target).sum()
                        )
                        witness_valid = construction_residual <= 1e-12
                    elif label == "near_boundary":
                        point_index, coordinate = np.unravel_index(
                            np.argmin(alternatives), alternatives.shape
                        )
                        target = alternatives[point_index].copy()
                        epsilon = min(1e-7, target[coordinate] / 2)
                        other = (coordinate + 1) % target.size
                        target[coordinate] -= epsilon
                        target[other] += epsilon
                        analytic_margin = float(
                            alternatives[:, coordinate].min()
                            - target[coordinate]
                        )
                        witness_valid = analytic_margin > 0
                    else:
                        coordinate = int(rng.integers(0, dimension))
                        target = np.eye(dimension)[coordinate]
                        analytic_margin = float(
                            target[coordinate]
                            - alternatives[:, coordinate].max()
                        )
                        witness_valid = analytic_margin > 0

                    started = time.perf_counter()
                    distance, coefficients_fit = l1_distance_to_hull(
                        target, alternatives
                    )
                    runtime_ms = (time.perf_counter() - started) * 1000
                    prediction = (
                        "replaceable"
                        if distance <= args.tolerance
                        else "separable"
                    )
                    rows.append({
                        "trial": trial,
                        "seed": seed,
                        "dimension": dimension,
                        "alternative_count": alternative_count,
                        "repetition": repetition,
                        "true_class": label,
                        "predicted_class": prediction,
                        "l1_distance": distance,
                        "construction_epsilon": epsilon,
                        "construction_residual_l1": construction_residual,
                        "analytic_separation_margin": analytic_margin,
                        "ground_truth_witness_valid": witness_valid,
                        "tolerance": args.tolerance,
                        "runtime_ms": runtime_ms,
                        "coefficient_sum": float(coefficients_fit.sum()),
                    })
                    if label == "near_boundary":
                        for tolerance in (1e-10, 1e-8, 1e-6):
                            tolerance_rows.append({
                                "trial": trial,
                                "seed": seed,
                                "dimension": dimension,
                                "alternative_count": alternative_count,
                                "l1_distance": distance,
                                "analytic_separation_margin": analytic_margin,
                                "tolerance": tolerance,
                                "classification": (
                                    "replaceable"
                                    if distance <= tolerance
                                    else "separable"
                                ),
                            })
                    trial += 1

    ensure_results()
    fields = [
        "trial", "seed", "dimension", "alternative_count", "repetition",
        "true_class", "predicted_class", "l1_distance",
        "construction_epsilon", "construction_residual_l1",
        "analytic_separation_margin", "ground_truth_witness_valid",
        "tolerance", "runtime_ms", "coefficient_sum",
    ]
    write_csv(RESULTS / "replacement_hull_trials.csv", rows, fields)
    write_csv(
        RESULTS / "replacement_hull_tolerance_sweep.csv",
        tolerance_rows,
        [
            "trial", "seed", "dimension", "alternative_count", "l1_distance",
            "analytic_separation_margin", "tolerance", "classification",
        ],
    )
    exact_errors = sum(
        row["true_class"] == "replaceable"
        and row["predicted_class"] != "replaceable"
        for row in rows
    )
    separable_errors = sum(
        row["true_class"] == "separable"
        and row["predicted_class"] != "separable"
        for row in rows
    )
    witness_failures = sum(
        not row["ground_truth_witness_valid"] for row in rows
    )
    clear_trials = sum(
        row["true_class"] in {"replaceable", "separable"} for row in rows
    )
    clear_errors = exact_errors + separable_errors
    near = [
        row["l1_distance"]
        for row in rows
        if row["true_class"] == "near_boundary"
    ]
    scale_summary = {}
    for dimension, alternative_count in scales:
        selected = [
            row["runtime_ms"]
            for row in rows
            if row["dimension"] == dimension
            and row["alternative_count"] == alternative_count
        ]
        selected.sort()
        scale_summary[f"d{dimension}_k{alternative_count}"] = {
            "trials": len(selected),
            "runtime_ms_median": float(np.median(selected)),
            "runtime_ms_p95": float(np.quantile(selected, 0.95)),
            "runtime_ms_max": max(selected),
        }
    tolerance_counts = defaultdict(lambda: {"replaceable": 0, "separable": 0})
    for row in tolerance_rows:
        tolerance_counts[str(row["tolerance"])][row["classification"]] += 1
    seed_summary = {}
    for seed in args.seeds:
        selected = [row for row in rows if row["seed"] == seed]
        selected_clear = [
            row for row in selected
            if row["true_class"] in {"replaceable", "separable"}
        ]
        selected_errors = sum(
            row["predicted_class"] != row["true_class"]
            for row in selected_clear
        )
        seed_summary[str(seed)] = {
            "trials": len(selected),
            "clear_trials": len(selected_clear),
            "clear_errors": selected_errors,
            "ground_truth_witness_failures": sum(
                not row["ground_truth_witness_valid"] for row in selected
            ),
        }
    write_json(
        RESULTS / "replacement_hull_summary.json",
        {
            "seeds": list(args.seeds),
            "trials": len(rows),
            "clear_trials": clear_trials,
            "tolerance": args.tolerance,
            "solver": {
                "method": "scipy.optimize.linprog-highs",
                "primal_feasibility_tolerance": 1e-10,
                "dual_feasibility_tolerance": 1e-10,
                "ipm_optimality_tolerance": 1e-12,
            },
            "exact_replaceable_errors": exact_errors,
            "clear_separable_errors": separable_errors,
            "clear_classification_errors": clear_errors,
            "clear_classification_error_rate": clear_errors / clear_trials,
            "clear_error_rate_wilson_95_upper": wilson_upper(
                clear_errors, clear_trials
            ),
            "ground_truth_witness_failures": witness_failures,
            "near_boundary_min_distance": min(near),
            "near_boundary_max_distance": max(near),
            "runtime_by_scale": scale_summary,
            "results_by_seed": seed_summary,
            "near_boundary_classification_by_tolerance": dict(tolerance_counts),
            "ground_truth_note": (
                "Replaceable labels carry an explicit convex-combination "
                "witness. Separable labels carry an analytic supporting-"
                "coordinate margin independent of the LP output."
            ),
            "warning": (
                "Near-boundary classifications depend on the declared numerical "
                "tolerance and must be reported with the distance."
            ),
        },
    )


if __name__ == "__main__":
    main()
