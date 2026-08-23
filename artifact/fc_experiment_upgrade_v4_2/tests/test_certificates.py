import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from certificates import mabc, mixed_cover, threshold_cover


def instance():
    return (
        [4, 4, 1, 1, 1, 1, 1],
        [1 / 7] * 7,
        4 / 7,
        [0, 0, 2 / 7, 2 / 7, 2 / 7, 2 / 7, 2 / 7],
    )


def test_pinned_boundaries():
    resistance, weights, threshold, activation = instance()
    assert threshold_cover(resistance, weights, threshold) == 4
    assert mixed_cover(
        resistance, weights, threshold, activation, set(range(7))
    ) == 10


def test_pinned_atomic_curve():
    resistance, weights, threshold, activation = instance()
    curve = [
        mabc(
            resistance, weights, threshold, activation, set(range(7)), budget
        )
        for budget in range(8)
    ]
    assert curve == [10, 7, 4, 4, 4, 4, 4, 4]


def test_partial_evidence_jump():
    resistance, weights, threshold, activation = instance()
    assert mixed_cover(
        resistance, weights, threshold, activation, {2, 3, 4}
    ) == 4
    assert mixed_cover(
        resistance, weights, threshold, activation, {2, 3, 4, 5}
    ) == 7


def test_heterogeneous_identity_matters_at_equal_evidence_count():
    resistance = [4, 3, 2, 7, 1, 8]
    weights = [3 / 13, 2 / 13, 3 / 13, 2 / 13, 2 / 13, 1 / 13]
    activation = [0.45, 0, 0.35, 0, 0, 0.15]
    threshold = 0.6
    assert mixed_cover(
        resistance, weights, threshold, activation, {0}
    ) == 10
    assert mixed_cover(
        resistance, weights, threshold, activation, {1}
    ) == 7


def test_false_floor_promotion_inflates_public_certificate():
    resistance, weights, threshold, activation = instance()
    true_resistance = [0] * 7
    assert mixed_cover(
        true_resistance,
        weights,
        threshold,
        activation,
        set(range(7)),
    ) == 0
    assert mixed_cover(
        resistance,
        weights,
        threshold,
        activation,
        set(range(7)),
    ) == 10
