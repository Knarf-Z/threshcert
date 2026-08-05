from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ptr_exp.witness import (  # noqa: E402
    AggregationWitness,
    AllocationEntry,
    AllocationWitness,
    bitmap_of,
    ids_of_bitmap,
    verify_allocation_witness,
)


def _aggregation(ids=(1, 2, 3, 4)) -> AggregationWitness:
    return AggregationWitness(
        order_id="o1",
        buyer="b",
        resource="r",
        epoch=1,
        responder_bitmap=bitmap_of(ids),
        operator_ids=tuple(ids),
        partial_response_hashes=tuple(f"h{i}" for i in ids),
        aggregate_valid=True,
        plaintext_hash="p",
    )


def _entry(operator_id: int, bitmap: str, debit: int, debit_id: str | None = None) -> AllocationEntry:
    return AllocationEntry(
        operator_id=operator_id,
        responder_bitmap=bitmap,
        response_hash=f"h{operator_id}",
        debit_id=debit_id or f"d{operator_id}",
        debit=debit,
        refund_ids=(),
        refund=0,
        funding_ids=(),
        external_funding=0,
    )


class BitmapTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        for ids in ([1, 2, 3, 4], [4, 5, 6, 7], [1, 7]):
            self.assertEqual(ids_of_bitmap(bitmap_of(ids)), sorted(ids))

    def test_rejects_zero_index(self) -> None:
        with self.assertRaises(ValueError):
            bitmap_of([0])


class AllocationWitnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.floors = {1: 1, 2: 2, 3: 3, 4: 4}

    def test_accepts_disjoint_covering_allocation(self) -> None:
        aggregation = _aggregation()
        entries = tuple(_entry(i, aggregation.responder_bitmap, self.floors[i]) for i in (1, 2, 3, 4))
        allocation = AllocationWitness("o1", aggregation.responder_bitmap, entries)
        check = verify_allocation_witness(aggregation, allocation, self.floors, 10)
        self.assertTrue(check.ok, check.failures)
        self.assertEqual(allocation.total_allocated, 10)

    def test_rejects_reused_debit_id(self) -> None:
        aggregation = _aggregation()
        entries = tuple(
            _entry(i, aggregation.responder_bitmap, self.floors[i], debit_id="shared") for i in (1, 2, 3, 4)
        )
        allocation = AllocationWitness("o1", aggregation.responder_bitmap, entries)
        check = verify_allocation_witness(aggregation, allocation, self.floors, 10)
        self.assertFalse(check.ok)
        self.assertTrue(any("allocated more than once" in f for f in check.failures))

    def test_rejects_allocation_exceeding_outflow(self) -> None:
        aggregation = _aggregation()
        entries = tuple(_entry(i, aggregation.responder_bitmap, self.floors[i]) for i in (1, 2, 3, 4))
        allocation = AllocationWitness("o1", aggregation.responder_bitmap, entries)
        check = verify_allocation_witness(aggregation, allocation, self.floors, 9)
        self.assertFalse(check.ok)
        self.assertTrue(any("exceeds the realized outflow" in f for f in check.failures))

    def test_rejects_floor_shortfall(self) -> None:
        aggregation = _aggregation()
        entries = tuple(_entry(i, aggregation.responder_bitmap, 0) for i in (1, 2, 3, 4))
        allocation = AllocationWitness("o1", aggregation.responder_bitmap, entries)
        check = verify_allocation_witness(aggregation, allocation, self.floors, 10)
        self.assertFalse(check.ok)
        self.assertTrue(any("below its floor" in f for f in check.failures))

    def test_rejects_foreign_bitmap(self) -> None:
        aggregation = _aggregation()
        other = bitmap_of([4, 5, 6, 7])
        entries = tuple(_entry(i, other, self.floors[i]) for i in (1, 2, 3, 4))
        allocation = AllocationWitness("o1", other, entries)
        check = verify_allocation_witness(aggregation, allocation, self.floors, 10)
        self.assertFalse(check.ok)
        self.assertTrue(any("bitmap mismatch" in f for f in check.failures))

    def test_rejects_hash_mismatch(self) -> None:
        aggregation = _aggregation()
        entries = list(_entry(i, aggregation.responder_bitmap, self.floors[i]) for i in (1, 2, 3, 4))
        bad = entries[0]
        entries[0] = AllocationEntry(
            operator_id=bad.operator_id,
            responder_bitmap=bad.responder_bitmap,
            response_hash="tampered",
            debit_id=bad.debit_id,
            debit=bad.debit,
            refund_ids=bad.refund_ids,
            refund=bad.refund,
            funding_ids=bad.funding_ids,
            external_funding=bad.external_funding,
        )
        allocation = AllocationWitness("o1", aggregation.responder_bitmap, tuple(entries))
        check = verify_allocation_witness(aggregation, allocation, self.floors, 10)
        self.assertFalse(check.ok)
        self.assertTrue(any("response hash differs" in f for f in check.failures))


if __name__ == "__main__":
    unittest.main()
