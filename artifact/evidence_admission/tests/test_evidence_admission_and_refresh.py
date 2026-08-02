from __future__ import annotations

import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_floor_admission_experiment import (  # noqa: E402
    FloorRecord,
    NOW,
    admit_floor,
    build_result as build_floor_result,
    complete_record,
)
from run_refresh_window_experiment import (  # noqa: E402
    build_result as build_refresh_result,
    erasure_window_cost,
    local_epoch_cost,
    persistent_window_cost,
)


class EvidenceAdmissionTests(unittest.TestCase):
    def test_reported_floor_is_not_admitted_evidence(self) -> None:
        record = FloorRecord(member=0, reported_floor=10**30, signer_bound=True)
        value, failures = admit_floor(record)
        self.assertEqual(value, 0)
        self.assertIn("MEMBER_OWNERSHIP_MISSING", failures)

    def test_complete_backing_is_net_of_offsets(self) -> None:
        record = complete_record(0, 5, report=10**30)
        self.assertEqual(admit_floor(record), (5, []))
        inflated = FloorRecord(**{**asdict(record), "reported_floor": 10**60})
        self.assertEqual(admit_floor(inflated), (5, []))

    def test_expiry_and_revocation_fail_closed(self) -> None:
        record = complete_record(0, 5)
        expired = FloorRecord(**{**asdict(record), "valid_until": NOW - 1})
        revoked = FloorRecord(**{**asdict(record), "revoked": True})
        self.assertEqual(admit_floor(expired)[0], 0)
        self.assertEqual(admit_floor(revoked)[0], 0)

    def test_missing_member_attribution_fails_closed(self) -> None:
        record = complete_record(0, 5)
        unattributed = FloorRecord(
            **{**asdict(record), "member_attribution_bound": False}
        )
        value, failures = admit_floor(unattributed)
        self.assertEqual(value, 0)
        self.assertIn("MEMBER_ATTRIBUTION_MISSING", failures)

    def test_recorded_floor_result_is_current(self) -> None:
        recorded = json.loads(
            (ROOT / "results" / "floor_admission_experiment.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(recorded, build_floor_result())


class RefreshWindowTests(unittest.TestCase):
    def test_paired_world_requires_erasure_evidence(self) -> None:
        costs = [1] * 7
        latencies = [2] * 7
        durations = [6, 6]
        self.assertIsNone(erasure_window_cost(costs, latencies, 4, durations))
        self.assertEqual(persistent_window_cost(costs, latencies, 4, durations), 4)

    def test_shorter_epoch_cannot_lower_local_cost(self) -> None:
        costs = [1, 1, 1, 1, 5, 5, 5]
        latencies = [3, 3, 3, 3, 1, 1, 1]
        values = [local_epoch_cost(costs, latencies, 4, duration) for duration in range(1, 17)]
        ranks = [float("inf") if value is None else value for value in values]
        self.assertTrue(all(a >= b for a, b in zip(ranks, ranks[1:])))

    def test_recorded_refresh_result_is_current(self) -> None:
        recorded = json.loads(
            (ROOT / "results" / "refresh_window_experiment.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(recorded, build_refresh_result())


if __name__ == "__main__":
    unittest.main()
