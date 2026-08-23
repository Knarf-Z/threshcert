from __future__ import annotations

from itertools import combinations

from common import RESULTS, ensure_results, write_csv, write_json
from certificates import mixed_cover


def add_subset_rows(
    rows,
    fixture,
    resistance,
    weights,
    threshold,
    activation,
    floor_members,
    baseline,
):
    summary = {}
    for count in range(len(floor_members) + 1):
        values = []
        for selected in combinations(floor_members, count):
            value = mixed_cover(
                resistance,
                weights,
                threshold,
                activation,
                set(selected),
            )
            values.append((selected, value))
            rows.append({
                "fixture": fixture,
                "experiment": "activation_evidence_subset",
                "evidence_count": count,
                "members": ";".join(map(str, selected)),
                "certificate": value,
                "baseline_correct_certificate": baseline,
                "false_elevation": value - baseline,
            })
        certificates = [value for _, value in values]
        summary[str(count)] = {
            "min": min(certificates),
            "max": max(certificates),
            "distinct_values": len(set(certificates)),
            "argmin_example": ";".join(map(str, min(values, key=lambda x: x[1])[0])),
            "argmax_example": ";".join(map(str, max(values, key=lambda x: x[1])[0])),
        }
    return summary


def main() -> None:
    rows = []

    # Symmetric pinned counterfactual: isolates pure evidence complementarity.
    resistance = [4, 4, 1, 1, 1, 1, 1]
    weights = [1 / 7] * 7
    activation = [0, 0, 2 / 7, 2 / 7, 2 / 7, 2 / 7, 2 / 7]
    threshold = 4 / 7
    floor_members = [2, 3, 4, 5, 6]
    symmetric_summary = add_subset_rows(
        rows,
        "symmetric_pinned_counterfactual",
        resistance,
        weights,
        threshold,
        activation,
        floor_members,
        4,
    )

    # Heterogeneous fixture: equal evidence counts can select very different
    # members and therefore produce different certificate values.
    hetero_resistance = [4, 3, 2, 7, 1, 8]
    hetero_weights = [3 / 13, 2 / 13, 3 / 13, 2 / 13, 2 / 13, 1 / 13]
    hetero_activation = [0.45, 0, 0.35, 0, 0, 0.15]
    hetero_summary = add_subset_rows(
        rows,
        "heterogeneous_identity_fixture",
        hetero_resistance,
        hetero_weights,
        0.6,
        hetero_activation,
        list(range(6)),
        7,
    )

    # False certification: uncertified estimates are incorrectly promoted to floors.
    true_resistance = [0] * 7
    estimated_resistance = resistance
    false_promotion_curve = []
    for promoted in range(8):
        used = [
            estimated_resistance[i] if i < promoted else true_resistance[i]
            for i in range(7)
        ]
        value = mixed_cover(
            used, weights, threshold, activation, set(range(7))
        )
        false_promotion_curve.append(value)
        rows.append({
            "fixture": "symmetric_pinned_counterfactual",
            "experiment": "false_resistance_promotion",
            "evidence_count": promoted,
            "members": ";".join(map(str, range(promoted))),
            "certificate": value,
            "baseline_correct_certificate": 0,
            "false_elevation": value,
        })

    ensure_results()
    fields = [
        "fixture", "experiment", "evidence_count", "members", "certificate",
        "baseline_correct_certificate", "false_elevation",
    ]
    write_csv(RESULTS / "evidence_sensitivity.csv", rows, fields)

    write_json(
        RESULTS / "evidence_sensitivity_summary.json",
        {
            "symmetric_complementarity": symmetric_summary,
            "heterogeneous_identity_effect": hetero_summary,
            "full_activation_certificate": symmetric_summary["5"]["max"],
            "correct_public_only_certificate": 0,
            "false_resistance_promotion_curve": false_promotion_curve,
            "maximum_false_elevation": max(false_promotion_curve),
            "interpretation": (
                "The symmetric fixture isolates a plateau through three floors "
                "followed by jumps at four and five. The heterogeneous fixture "
                "separately shows that equal evidence counts can yield different "
                "values because member identity and substitute covers matter. "
                "Promoting uncertified estimates to resistance floors can raise "
                "a correct zero certificate to a spurious positive value."
            ),
        },
    )


if __name__ == "__main__":
    main()
