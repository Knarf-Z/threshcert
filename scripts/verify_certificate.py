#!/usr/bin/env python3
"""Compute a resistance-only threshold-cover certificate for a uniform q-of-n snapshot."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path


def read_snapshot(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_resistances(path: Path) -> list[float]:
    values: list[float] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = (row.get("certified_resistance") or row.get("resistance_lower_bound") or "").strip()
            if raw:
                values.append(float(raw))
            else:
                values.append(0.0)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--target", type=float, default=None)
    args = parser.parse_args()

    snapshot = read_snapshot(args.snapshot)
    q = int(snapshot["threshold_count"])
    values = read_resistances(args.ledger)
    if len(values) != int(snapshot["committee_size"]):
        raise SystemExit("ledger length does not match committee_size")

    ordered = sorted(values)
    certificate = sum(ordered[:q])
    print(f"threshold_count={q}")
    print("ordered_certified_resistances=" + ",".join(f"{x:g}" for x in ordered))
    print(f"threshold_cover_certificate={certificate:g}")
    if args.target is not None:
        print(f"target={args.target:g}")
        print("decision=" + ("ACCEPT" if certificate >= args.target else "REJECT"))
    if snapshot.get("provenance_status") != "complete":
        print("provenance_warning=" + snapshot.get("provenance_limitation", "incomplete provenance"))


if __name__ == "__main__":
    main()
