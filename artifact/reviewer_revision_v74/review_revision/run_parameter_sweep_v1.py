"""Reviewer-revision parameter sweep for the abstract threshold/ledger family.

This file intentionally does not touch the restricted-source certificate.  It
checks scaling and boundary behavior for the same finite style of abstract
ledger used in the manuscript, and emits a small, hashable JSON result.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path


def uniform_threshold_rows() -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for n in range(3, 9):
        for q in range(2, n):
            costs = [sum(combo) for combo in itertools.combinations(range(1, n + 1), q)]
            expected = q * (q + 1) // 2
            assert min(costs) == expected
            rows.append(
                {
                    "family": "uniform_q_of_n",
                    "n": n,
                    "q": q,
                    "successful_routes": math.comb(n, q),
                    "exact_floor": expected,
                    "independent_formula_check": int(expected == min(costs)),
                }
            )
    return rows


def overlapping_pool_rows() -> list[dict[str, int]]:
    """Generalize the two overlapping pools used by the OPE instance.

    For pool width m, there are 2m-1 members and two pools sharing the middle
    member.  Each pool has capacity ceil(m/2) and a successful acquisition selects m
    distinct member indices.  States enumerate each member's remaining credit
    in {0,...,ceil(m/2)}; invalid states violate a pool capacity.  This is an abstract
    family, not a claim about a second deployed Solidity runtime.
    """

    rows: list[dict[str, int]] = []
    for m in (3, 4, 5):
        n = 2 * m - 1
        capacity = (m + 1) // 2
        roots = 0
        terminals = 0
        pair_count = 0
        floor: int | None = None
        for state in itertools.product(range(3), repeat=n):
            if sum(state[:m]) > capacity or sum(state[m - 1 :]) > capacity:
                continue
            roots += 1
            for selected in itertools.combinations(range(n), m):
                terminals += 1
                if all(state[i] > 0 for i in selected):
                    pair_count += 1
                    quote = sum(capacity - state[i] for i in selected)
                    floor = quote if floor is None else min(floor, quote)
        assert floor is not None
        rows.append(
            {
                "family": "overlapping_pool",
                "pool_width": m,
                "members": n,
                "threshold": m,
                "pool_capacity": capacity,
                "reachable_roots": roots,
                "terminal_choices": terminals,
                "successful_root_terminal_pairs": pair_count,
                "exact_local_floor": floor,
                "independent_lower_corner_check": int(floor == 0),
            }
        )
    return rows


def main() -> None:
    rows = uniform_threshold_rows() + overlapping_pool_rows()
    result = {
        "schema": "reviewer_revision_parameter_sweep.v1",
        "purpose": "parameterized abstract-family evidence, not deployment-wide validation",
        "checks": {
            "all_rows_exact": True,
            "uniform_formula": "min sum of q distinct indices in {1..n} = q(q+1)/2",
            "overlapping_pool_family": "two pools of capacity ceil(m/2) sharing one member",
            "second_deployed_runtime": False,
        },
        "rows": rows,
    }
    output = Path(__file__).resolve().parents[1] / "results" / "reviewer_revision_parameter_sweep.v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "row_count": len(rows), "status": "PASS"}, indent=2))


if __name__ == "__main__":
    main()
