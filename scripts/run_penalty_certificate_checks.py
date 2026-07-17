#!/usr/bin/env python3
"""Check the evidence gates for penalty-backed resistance."""
from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "results" / "penalty_certificate_checks.csv"
TARGET = 10_000.0


def is_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def certified_resistance(row: dict[str, str]) -> float:
    base = float(row["base_resistance"])
    evidence_complete = all(
        is_true(row[field])
        for field in (
            "forfeiture_certified",
            "attribution_certified",
            "enforcement_certified",
        )
    )
    if not evidence_complete:
        return base
    return base + float(row["p_lower"]) * float(row["nominal_penalty"])


def evaluate(path: Path, q: int) -> tuple[list[float], float]:
    with path.open(newline="", encoding="utf-8") as handle:
        values = [certified_resistance(row) for row in csv.DictReader(handle)]
    if len(values) != 7:
        raise AssertionError("controlled penalty ledger must have seven members")
    ordered = sorted(values)
    return ordered, sum(ordered[:q])


def main() -> None:
    with (DATA / "shutter_keyper_snapshot.json").open(encoding="utf-8") as handle:
        q = int(json.load(handle)["threshold_count"])

    scenarios = [
        ("all_evidence_complete", DATA / "evidence_ledger_controlled_penalty.csv"),
        (
            "one_member_unattributable",
            DATA / "evidence_ledger_controlled_penalty_one_unattributable.csv",
        ),
    ]
    rows = []
    for scenario, path in scenarios:
        ordered, certificate = evaluate(path, q)
        rows.append(
            (
                scenario,
                q,
                ";".join(f"{value:g}" for value in ordered),
                certificate,
                TARGET,
                "ACCEPT" if certificate >= TARGET else "REJECT",
                "controlled; not deployment evidence",
            )
        )

    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scenario",
                "threshold_count",
                "ordered_certified_resistances",
                "certificate",
                "target",
                "decision",
                "interpretation",
            ]
        )
        writer.writerows(rows)

    expected = {
        "all_evidence_complete": (10_000.0, "ACCEPT"),
        "one_member_unattributable": (7_500.0, "REJECT"),
    }
    passed = sum(
        (certificate, decision) == expected[scenario]
        for scenario, _, _, certificate, _, decision, _ in rows
    )
    print(f"penalty_scenarios={len(rows)}")
    print(f"penalty_scenarios_passed={passed}")
    print("penalty_interpretation=CONTROLLED_NOT_DEPLOYMENT_EVIDENCE")


if __name__ == "__main__":
    main()
