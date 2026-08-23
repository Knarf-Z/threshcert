from __future__ import annotations

from common import RESULTS, ensure_results, write_csv, write_json
from certificates import mabc


def main() -> None:
    resistance = [4, 4, 1, 1, 1, 1, 1]
    weights = [1 / 7] * 7
    activation = [0, 0, 2 / 7, 2 / 7, 2 / 7, 2 / 7, 2 / 7]
    constrained = set(range(7))
    threshold = 4 / 7

    curve = []
    for budget in range(8):
        value = mabc(
            resistance, weights, threshold, activation, constrained, budget
        )
        curve.append({"package_budget_b": budget, "certificate": value})

    repeated = []
    for per_call_b in (1, 2, 3):
        for calls in range(1, 8):
            effective_budget = min(per_call_b * calls, len(weights))
            value = mabc(
                resistance,
                weights,
                threshold,
                activation,
                constrained,
                effective_budget,
            )
            repeated.append({
                "per_call_budget": per_call_b,
                "invocation_budget": calls,
                "effective_union_budget": effective_budget,
                "certificate": value,
            })

    ensure_results()
    write_csv(
        RESULTS / "atomic_bypass_curve.csv",
        curve,
        ["package_budget_b", "certificate"],
    )
    write_csv(
        RESULTS / "atomic_bypass_repetition.csv",
        repeated,
        [
            "per_call_budget", "invocation_budget",
            "effective_union_budget", "certificate",
        ],
    )
    expected = [10, 7, 4, 4, 4, 4, 4, 4]
    observed = [row["certificate"] for row in curve]
    if observed != expected:
        raise AssertionError(f"Unexpected pinned curve: {observed}")
    write_json(
        RESULTS / "atomic_bypass_summary.json",
        {
            "pinned_curve": observed,
            "matches_paper_curve": True,
            "repeated_singletons_reach_threshold_cover": (
                next(
                    row["certificate"]
                    for row in repeated
                    if row["per_call_budget"] == 1
                    and row["invocation_budget"] == 2
                ) == 4
            ),
            "scope_warning": (
                "Execution feasibility does not establish that production "
                "Keypers accept an atomic offer. The Solidity experiment uses "
                "an attested boundary whose trusted process must perform the "
                "native Rolling Shutter checks off chain; it is not direct "
                "on-chain BLS verification."
            ),
        },
    )


if __name__ == "__main__":
    main()
