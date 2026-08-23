import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from replacement_hull import l1_distance_to_hull, parse_seeds, wilson_upper


def test_exact_hull_membership():
    alternatives = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    target = np.array([0.2, 0.3, 0.5])
    distance, coefficients = l1_distance_to_hull(target, alternatives)
    assert distance < 1e-10
    assert abs(coefficients.sum() - 1) < 1e-10


def test_separation():
    alternatives = np.array([[0.5, 0.5, 0], [0.3, 0.7, 0]], dtype=float)
    target = np.array([0, 0, 1], dtype=float)
    distance, _ = l1_distance_to_hull(target, alternatives)
    assert distance > 1.9


def test_near_boundary_classification_depends_on_tolerance():
    alternatives = np.array(
        [[0.2, 0.3, 0.5], [0.4, 0.2, 0.4], [0.3, 0.4, 0.3]],
        dtype=float,
    )
    target = alternatives[0].copy()
    target[0] -= 1e-7
    target[1] += 1e-7
    distance, _ = l1_distance_to_hull(target, alternatives)
    assert distance > 1e-8
    assert distance < 1e-6


def test_multiple_seed_parser_rejects_duplicates():
    assert parse_seeds("1, 2,3") == (1, 2, 3)
    try:
        parse_seeds("1,1")
    except Exception:
        pass
    else:
        raise AssertionError("duplicate seeds were accepted")


def test_zero_error_wilson_upper_bound_is_nonzero():
    upper = wilson_upper(0, 2400)
    assert 0.0015 < upper < 0.0017
