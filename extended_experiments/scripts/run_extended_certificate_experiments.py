#!/usr/bin/env python3
"""Scalability, parameter-sensitivity, and simple-baseline experiments."""
from __future__ import annotations

import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SCALING_INPUT = ROOT / "inputs" / "solver_scaling_repeats_summary.csv"

RESISTANCE_PROFILES: dict[str, tuple[int, ...]] = {
    "uniform": (10, 10, 10, 10, 10, 10, 10),
    "balanced": (7, 8, 9, 10, 11, 12, 13),
    "bimodal": (4, 4, 4, 4, 18, 18, 18),
    "heavy_lower_tail": (1, 3, 6, 8, 11, 16, 25),
}
THRESHOLD_SHARES = (3, 4, 5, 6)
EXPOSURE_SHARES = (0, 1, 2)

BOUNDARY_RESISTANCE_PROFILES: dict[str, tuple[int, ...]] = {
    "all_zero": (0, 0, 0, 0, 0, 0, 0),
    "single_dominant_member": (100, 1, 1, 1, 1, 1, 1),
}
DEGENERATE_THRESHOLD_SHARES = (1, 7)
LARGER_COMMITTEE_SIZES = (14, 28)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def exact_uniform_certificate(resistances: tuple[int, ...], required: int) -> int:
    if not 1 <= required <= len(resistances):
        raise ValueError("required share count must be within the committee")
    return sum(sorted(resistances)[:required])


def scalability_analysis() -> list[dict[str, object]]:
    with SCALING_INPUT.open(newline="", encoding="utf-8") as handle:
        source = list(csv.DictReader(handle))
    rows: list[dict[str, object]] = []
    previous_states: int | None = None
    previous_median: float | None = None
    for item in source:
        n = int(item["n"])
        states = int(item["subset_states"])
        median = float(item["median_seconds"])
        peak_mib = float(item["peak_mib"])
        rows.append(
            {
                "algorithm": "exact_activation_subset_state",
                "n": n,
                "runs": int(item["runs"]),
                "subset_states": states,
                "state_growth_vs_previous": ""
                if previous_states is None
                else f"{states / previous_states:.6f}",
                "median_seconds": f"{median:.9f}",
                "runtime_growth_vs_previous": ""
                if previous_median is None
                else f"{median / previous_median:.6f}",
                "median_nanoseconds_per_state": f"{median * 1e9 / states:.6f}",
                "q1_seconds": item["q1_seconds"],
                "q3_seconds": item["q3_seconds"],
                "peak_mib": f"{peak_mib:.9f}",
                "peak_bytes_per_state": f"{peak_mib * 1024 * 1024 / states:.6f}",
            }
        )
        previous_states = states
        previous_median = median
    write_rows(
        RESULTS / "scalability_analysis.csv",
        [
            "algorithm",
            "n",
            "runs",
            "subset_states",
            "state_growth_vs_previous",
            "median_seconds",
            "runtime_growth_vs_previous",
            "median_nanoseconds_per_state",
            "q1_seconds",
            "q3_seconds",
            "peak_mib",
            "peak_bytes_per_state",
        ],
        rows,
    )
    return rows


def certificate_cost_models() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for n in (7, 14, 28, 56, 112, 224, 448):
        required = math.ceil(4 * n / 7)
        rows.append(
            {
                "n": n,
                "threshold": "4/7",
                "required_shares": required,
                "uniform_lower_tail_sort_upper_bound": n * math.ceil(math.log2(n)),
                "uniform_input_items": n,
                "generic_subset_states": 1 << n,
                "uniform_complexity": "O(n log n)",
                "generic_activation_complexity": "O(2^n)",
            }
        )
    write_rows(
        RESULTS / "certificate_cost_models.csv",
        [
            "n",
            "threshold",
            "required_shares",
            "uniform_lower_tail_sort_upper_bound",
            "uniform_input_items",
            "generic_subset_states",
            "uniform_complexity",
            "generic_activation_complexity",
        ],
        rows,
    )
    return rows


def parameter_sensitivity() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    n = 7
    for profile, resistances in RESISTANCE_PROFILES.items():
        mean = sum(resistances) / n
        for threshold_shares in THRESHOLD_SHARES:
            for exposure_shares in EXPOSURE_SHARES:
                required = threshold_shares - exposure_shares
                certificate = exact_uniform_certificate(resistances, required)
                rows.append(
                    {
                        "profile": profile,
                        "n": n,
                        "resistances": ";".join(map(str, resistances)),
                        "mean_resistance": f"{mean:.6f}",
                        "minimum_resistance": min(resistances),
                        "threshold_shares": threshold_shares,
                        "threshold_fraction": f"{threshold_shares}/7",
                        "initial_exposure_shares": exposure_shares,
                        "initial_exposure_fraction": f"{exposure_shares}/7",
                        "required_additional_shares": required,
                        "exact_certificate": certificate,
                        "certificate_per_required_share": f"{certificate / required:.6f}",
                        "relative_to_uniform_profile": f"{certificate / (10 * required):.6f}",
                    }
                )
    write_rows(
        RESULTS / "parameter_sensitivity.csv",
        [
            "profile",
            "n",
            "resistances",
            "mean_resistance",
            "minimum_resistance",
            "threshold_shares",
            "threshold_fraction",
            "initial_exposure_shares",
            "initial_exposure_fraction",
            "required_additional_shares",
            "exact_certificate",
            "certificate_per_required_share",
            "relative_to_uniform_profile",
        ],
        rows,
    )
    return rows


def tile_profile(profile: tuple[int, ...], n: int) -> tuple[int, ...]:
    base = len(profile)
    if n % base != 0:
        raise ValueError("committee size must be a multiple of the base profile length")
    return profile * (n // base)


def boundary_and_scale_sensitivity() -> list[dict[str, object]]:
    """Extreme-parameter and larger-committee cases.

    Kept in a separate output from the 48-row `parameter_sensitivity` table
    above so that table's existing row count and recorded numbers stay
    unchanged.
    """

    rows: list[dict[str, object]] = []
    n = 7

    for profile, resistances in RESISTANCE_PROFILES.items():
        for threshold_shares in DEGENERATE_THRESHOLD_SHARES:
            for exposure_shares in EXPOSURE_SHARES:
                required = threshold_shares - exposure_shares
                if not 1 <= required <= n:
                    continue
                rows.append(
                    {
                        "case": "degenerate_threshold_margin",
                        "profile": profile,
                        "n": n,
                        "threshold_shares": threshold_shares,
                        "initial_exposure_shares": exposure_shares,
                        "required_additional_shares": required,
                        "exact_certificate": exact_uniform_certificate(
                            resistances, required
                        ),
                    }
                )

    extended_threshold_shares = sorted(set(THRESHOLD_SHARES) | set(DEGENERATE_THRESHOLD_SHARES))
    for profile, resistances in BOUNDARY_RESISTANCE_PROFILES.items():
        for threshold_shares in extended_threshold_shares:
            for exposure_shares in EXPOSURE_SHARES:
                required = threshold_shares - exposure_shares
                if not 1 <= required <= n:
                    continue
                rows.append(
                    {
                        "case": "boundary_resistance_profile",
                        "profile": profile,
                        "n": n,
                        "threshold_shares": threshold_shares,
                        "initial_exposure_shares": exposure_shares,
                        "required_additional_shares": required,
                        "exact_certificate": exact_uniform_certificate(
                            resistances, required
                        ),
                    }
                )

    for size in LARGER_COMMITTEE_SIZES:
        for profile_name, base_resistances in RESISTANCE_PROFILES.items():
            resistances = tile_profile(base_resistances, size)
            proportional_required = round(4 * size / 7)
            for required in sorted({proportional_required, size}):
                rows.append(
                    {
                        "case": "larger_committee",
                        "profile": profile_name,
                        "n": size,
                        "threshold_shares": required,
                        "initial_exposure_shares": 0,
                        "required_additional_shares": required,
                        "exact_certificate": exact_uniform_certificate(
                            resistances, required
                        ),
                    }
                )

    write_rows(
        RESULTS / "parameter_sensitivity_boundary.csv",
        [
            "case",
            "profile",
            "n",
            "threshold_shares",
            "initial_exposure_shares",
            "required_additional_shares",
            "exact_certificate",
        ],
        rows,
    )
    return rows


def baseline_comparison() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    methods = (
        "public_only",
        "minimum_member_floor",
        "exact_lower_tail",
        "mean_resistance_heuristic",
    )
    for profile, resistances in RESISTANCE_PROFILES.items():
        mean = sum(resistances) / len(resistances)
        for required in THRESHOLD_SHARES:
            exact = exact_uniform_certificate(resistances, required)
            values = {
                "public_only": 0.0,
                "minimum_member_floor": float(required * min(resistances)),
                "exact_lower_tail": float(exact),
                "mean_resistance_heuristic": required * mean,
            }
            for method in methods:
                certified = method != "mean_resistance_heuristic"
                rows.append(
                    {
                        "profile": profile,
                        "required_shares": required,
                        "method": method,
                        "value": f"{values[method]:.6f}",
                        "exact_certificate": exact,
                        "ratio_to_exact": f"{values[method] / exact:.6f}",
                        "certified_lower_bound": str(certified).lower(),
                        "basis": {
                            "public_only": "no member-level evidence",
                            "minimum_member_floor": "q times the global member floor",
                            "exact_lower_tail": "sum of q smallest certified resistances",
                            "mean_resistance_heuristic": "q times the committee mean",
                        }[method],
                    }
                )
    write_rows(
        RESULTS / "baseline_comparison.csv",
        [
            "profile",
            "required_shares",
            "method",
            "value",
            "exact_certificate",
            "ratio_to_exact",
            "certified_lower_bound",
            "basis",
        ],
        rows,
    )
    return rows


def main() -> None:
    scaling = scalability_analysis()
    cost_models = certificate_cost_models()
    sensitivity = parameter_sensitivity()
    boundary_sensitivity = boundary_and_scale_sensitivity()
    baselines = baseline_comparison()
    runtime_ratio = float(scaling[-1]["median_seconds"]) / float(
        scaling[0]["median_seconds"]
    )
    heavy = [
        row
        for row in sensitivity
        if row["profile"] == "heavy_lower_tail"
        and row["threshold_shares"] == 4
        and row["initial_exposure_shares"] == 0
    ][0]
    print(f"scalability_rows={len(scaling)}")
    print(f"n8_median_seconds={scaling[0]['median_seconds']}")
    print(f"n18_median_seconds={scaling[-1]['median_seconds']}")
    print(f"n18_over_n8_median_runtime={runtime_ratio:.6f}")
    print(f"cost_model_rows={len(cost_models)}")
    print(f"parameter_sensitivity_rows={len(sensitivity)}")
    print(f"heavy_lower_tail_4of7_certificate={heavy['exact_certificate']}")
    print(f"boundary_sensitivity_rows={len(boundary_sensitivity)}")
    print(f"baseline_rows={len(baselines)}")


if __name__ == "__main__":
    main()
