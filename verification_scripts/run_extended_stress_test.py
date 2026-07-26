#!/usr/bin/env python3
"""Additive, larger-scale rerun of this directory's own stress tests.

This does NOT change, rerun in place, or replace any of the individually
runnable scripts in this directory (test_equivalence.py,
information_boundary.py, partial_activation_evidence.py,
atomic_bypass_hierarchy.py, general_package_family_hierarchy.py,
evidence_optimal_atomic_bypass.py, mixed_evidence_atomic_bypass.py,
replacement_hull.py) or the "as last run" counts recorded in README.md --
those remain the record of what backs the paper's own citations.

Instead it imports each script's already-verified check_* functions and
calls them again with an 8x larger trials_per_n (same n_values, same
seed_base -- so every original instance is included as a strict prefix of
this run's instances, plus new ones beyond it), purely to accumulate more
random-instance evidence now that the parallel_map speedup (see core.py)
makes an 8x larger sweep finish in about the same wall-clock time the
original single-threaded default-scale sweep used to take. A genuinely new
counterexample here would matter; a clean pass here is additional
confidence, not a new claim -- it does not by itself extend what the paper
states was checked at n=3..7 (or wherever each script's own n_values stops).

Writes a summary to results/extended_stress_test.txt (created fresh each
run) and to stdout. Exits nonzero if anything found a mismatch/violation.
"""
from __future__ import annotations

import sys
import os
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_equivalence
import information_boundary
import partial_activation_evidence
import atomic_bypass_hierarchy
import general_package_family_hierarchy
import evidence_optimal_atomic_bypass
import mixed_evidence_atomic_bypass
import replacement_hull

SCALE = 8
RESULTS = Path(__file__).resolve().parent / "results"


def _run(name, fn, **kwargs):
    start = time.perf_counter()
    result = fn(**kwargs)
    elapsed = time.perf_counter() - start
    total = result[0]
    # Every check_* function returns (total, *problem_lists); replacement_hull's
    # test_formula_equivalence instead returns (checked, mismatch_count) as a
    # plain int, so count each remaining item as itself if it's not a list.
    problem_count = sum(
        len(x) if isinstance(x, list) else x for x in result[1:]
    )
    return name, total, problem_count, elapsed


def main() -> None:
    checks = []

    checks.append(_run(
        "test_equivalence.run", test_equivalence.run,
        trials_per_n=60 * SCALE,
    ))

    checks.append(_run(
        "information_boundary.check_tightness_and_soundness",
        information_boundary.check_tightness_and_soundness,
        trials_per_n=60 * SCALE,
    ))
    checks.append(_run(
        "information_boundary.check_public_only_layer",
        information_boundary.check_public_only_layer,
        trials_per_n=20 * SCALE,
    ))

    checks.append(_run(
        "partial_activation_evidence.check_boundary_and_monotonicity",
        partial_activation_evidence.check_boundary_and_monotonicity,
        trials_per_n=40 * SCALE,
    ))
    checks.append(_run(
        "partial_activation_evidence.check_tightness_and_soundness",
        partial_activation_evidence.check_tightness_and_soundness,
        trials_per_n=40 * SCALE,
    ))

    checks.append(_run(
        "atomic_bypass_hierarchy.check_cross_validation",
        atomic_bypass_hierarchy.check_cross_validation,
        trials_per_n=40 * SCALE,
    ))
    checks.append(_run(
        "atomic_bypass_hierarchy.check_boundaries_and_monotonicity",
        atomic_bypass_hierarchy.check_boundaries_and_monotonicity,
        trials_per_n=60 * SCALE,
    ))

    checks.append(_run(
        "general_package_family_hierarchy.check_general_cross_validation",
        general_package_family_hierarchy.check_general_cross_validation,
        trials_per_n=40 * SCALE,
    ))
    checks.append(_run(
        "general_package_family_hierarchy.check_cardinality_family_redundancy",
        general_package_family_hierarchy.check_cardinality_family_redundancy,
        trials_per_n=25 * SCALE,
    ))
    checks.append(_run(
        "general_package_family_hierarchy.check_full_collapse_with_singletons",
        general_package_family_hierarchy.check_full_collapse_with_singletons,
        trials_per_n=40 * SCALE,
    ))

    checks.append(_run(
        "evidence_optimal_atomic_bypass.check_tightness",
        evidence_optimal_atomic_bypass.check_tightness,
        trials_per_n=40 * SCALE,
    ))
    checks.append(_run(
        "evidence_optimal_atomic_bypass.check_soundness",
        evidence_optimal_atomic_bypass.check_soundness,
        trials_per_n=40 * SCALE,
    ))
    checks.append(_run(
        "evidence_optimal_atomic_bypass.check_public_only",
        evidence_optimal_atomic_bypass.check_public_only,
        trials_per_n=20 * SCALE,
    ))
    checks.append(_run(
        "evidence_optimal_atomic_bypass.check_resistance_only_collapses_to_tcr",
        evidence_optimal_atomic_bypass.check_resistance_only_collapses_to_tcr,
        trials_per_n=30 * SCALE,
    ))

    checks.append(_run(
        "mixed_evidence_atomic_bypass.check_mcr_formula_matches_brute_force",
        mixed_evidence_atomic_bypass.check_mcr_formula_matches_brute_force,
        trials_per_n=100 * SCALE,
    ))
    checks.append(_run(
        "mixed_evidence_atomic_bypass.check_tightness",
        mixed_evidence_atomic_bypass.check_tightness,
        trials_per_n=60 * SCALE,
    ))
    checks.append(_run(
        "mixed_evidence_atomic_bypass.check_soundness",
        mixed_evidence_atomic_bypass.check_soundness,
        trials_per_n=60 * SCALE,
    ))

    checks.append(_run(
        "replacement_hull.test_formula_equivalence(n=3,m=2)",
        replacement_hull.test_formula_equivalence,
        trials=30 * SCALE, n=3, m=2,
    ))
    checks.append(_run(
        "replacement_hull.test_formula_equivalence(n=4,m=3)",
        replacement_hull.test_formula_equivalence,
        trials=10 * SCALE, n=4, m=3,
    ))

    lines = [
        f"Extended stress test (scale={SCALE}x default trials_per_n, same "
        "n_values and seed_base as each script's own default -- every "
        "originally-tested instance is a strict prefix of this run's).",
        "",
    ]
    total_instances = 0
    total_problems = 0
    for name, total, problems, elapsed in checks:
        total_instances += total
        total_problems += problems
        lines.append(
            f"{name}: instances={total} problems={problems} seconds={elapsed:.2f}"
        )
    lines.append("")
    lines.append(f"grand_total_instances={total_instances}")
    lines.append(f"grand_total_problems={total_problems}")
    lines.append(f"extended_stress_test={'PASS' if total_problems == 0 else 'FAIL'}")

    report = "\n".join(lines)
    print(report)

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "extended_stress_test.txt").write_text(report + "\n", encoding="utf-8")

    if total_problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
