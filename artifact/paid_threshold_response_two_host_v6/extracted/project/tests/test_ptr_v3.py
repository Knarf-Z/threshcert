"""Unit tests for the v3 two-host modules.

These run without any operator process. Everything that needs the network is
covered by the experiment scripts instead; what is tested here is the part a
reviewer has to trust when reading the frozen JSON: that each proof object
rejects the specific violation it claims to rule out.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.certificate import brute_force_weighted, catalog_certificate, theory_cover, weighted_dp
from ptr_v3.crypto import (
    ThresholdKeySet,
    combine_partials,
    create_partial,
    encrypt_capability,
    verify_partial,
    verify_threshold_result,
)
from ptr_v3.evidence import (
    CERTIFIED,
    FAIL_CLOSED_MISSING_EVIDENCE,
    FAIL_COUNTEREXAMPLE,
    NOT_APPLICABLE,
    REFUTED,
    UNKNOWN,
    ExecutionView,
    evaluate,
)
from ptr_v3.dealer import deal, write_dealt
from ptr_v3.ledger import OrderLedger
from ptr_v3.network_identity import NetworkIdentity, OperatorRegistry, sign, signing_message, verify
from ptr_v3.witness import (
    AggregationWitness,
    AllocationEntry,
    AllocationWitness,
    RouteCoverageEvidence,
    bitmap_of,
    build_host_local_secret_file_placement_witness,
    build_separation_witness,
    ids_of_bitmap,
    verify_allocation_witness,
)

SIZE, THRESHOLD = 7, 4
FLOORS = (1, 2, 3, 4, 5, 6, 7)
HOSTS = {1: "host1", 3: "host1", 5: "host1", 2: "host2", 4: "host2", 6: "host2", 7: "host2"}


class CryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.keyset = ThresholdKeySet.generate(SIZE, THRESHOLD, seed=1)
        cls.ciphertext = encrypt_capability(cls.keyset.public_key, "buyer", "resource", "order-1", seed=2)

    def partial(self, operator_id: int, ciphertext=None, epoch: int = 1):
        return create_partial(
            operator_id,
            self.keyset.secret_shares[operator_id - 1],
            self.keyset.public_shares[operator_id - 1],
            ciphertext or self.ciphertext,
            epoch,
        )

    def test_any_threshold_subset_reconstructs(self) -> None:
        for coalition in ([1, 2, 3, 4], [4, 5, 6, 7], [1, 3, 5, 7], [2, 3, 6, 7]):
            plaintext = combine_partials(
                self.ciphertext, [self.partial(i) for i in coalition], THRESHOLD
            )
            self.assertTrue(verify_threshold_result(self.ciphertext, plaintext), coalition)

    def test_below_threshold_does_not_reconstruct(self) -> None:
        partials = [self.partial(i) for i in (1, 2, 3)]
        plaintext = combine_partials(self.ciphertext, partials, len(partials))
        self.assertFalse(verify_threshold_result(self.ciphertext, plaintext))

    def test_proof_verifies_against_the_registered_share(self) -> None:
        response = self.partial(3)
        self.assertTrue(verify_partial(self.keyset.public_shares[2], self.ciphertext, response, 1))

    def test_proof_fails_against_another_operators_share(self) -> None:
        response = self.partial(3)
        self.assertFalse(verify_partial(self.keyset.public_shares[4], self.ciphertext, response, 1))

    def test_proof_fails_under_a_different_epoch(self) -> None:
        response = self.partial(3, epoch=1)
        self.assertTrue(verify_partial(self.keyset.public_shares[2], self.ciphertext, response, 1))
        self.assertFalse(verify_partial(self.keyset.public_shares[2], self.ciphertext, response, 2))

    def test_tampered_partial_is_rejected(self) -> None:
        response = self.partial(3)
        forged = type(response).from_dict(
            {
                "operator_id": 3,
                "value": hex(response.value + 1),
                "proof": response.proof.to_dict(),
            }
        )
        self.assertFalse(verify_partial(self.keyset.public_shares[2], self.ciphertext, forged, 1))

    def test_proof_is_deterministic_for_the_same_statement(self) -> None:
        first = self.partial(3)
        second = self.partial(3)
        self.assertEqual(first.proof.to_dict(), second.proof.to_dict())

    def _candidate_share(self, p1, e1, p2, e2):
        from ptr_v3.crypto import Q, mod_inv

        return (p1.proof.z - p2.proof.z) * mod_inv((e1 - e2) % Q, Q) % Q

    def test_witness_differs_across_ciphertexts_no_share_leak(self) -> None:
        """The two-query share-extraction attack must be impossible.

        With a requester-chosen nonce, two statements answered under the same
        witness ``w`` give ``s = (z1 - z2)(e1 - e2)^{-1}``. The witness binds the
        full statement, so it differs and the recovered value is not the share.
        """
        from ptr_v3.crypto import _proof_challenge

        other = encrypt_capability(self.keyset.public_key, "buyer", "resource", "order-2", seed=7)
        p1, p2 = self.partial(3, self.ciphertext), self.partial(3, other)
        self.assertNotEqual(p1.proof.a1, p2.proof.a1)
        e1 = _proof_challenge(3, self.keyset.public_shares[2], self.ciphertext, 1, p1.value, p1.proof.a1, p1.proof.a2)
        e2 = _proof_challenge(3, self.keyset.public_shares[2], other, 1, p2.value, p2.proof.a1, p2.proof.a2)
        self.assertNotEqual(self._candidate_share(p1, e1, p2, e2), self.keyset.secret_shares[2])

    def test_same_c1c2_different_order_no_share_leak(self) -> None:
        """Same underlying (c1, c2) but a different order id must not reuse the
        witness, or two transcripts would expose the share."""
        from ptr_v3.crypto import Ciphertext, _proof_challenge

        base = self.ciphertext
        twin = Ciphertext(base.c1, base.c2, base.buyer, base.resource, "order-TWIN", base.plaintext_commitment)
        p1, p2 = self.partial(3, base), self.partial(3, twin)
        self.assertNotEqual(p1.proof.a1, p2.proof.a1)  # witness differs despite equal (c1, c2)
        e1 = _proof_challenge(3, self.keyset.public_shares[2], base, 1, p1.value, p1.proof.a1, p1.proof.a2)
        e2 = _proof_challenge(3, self.keyset.public_shares[2], twin, 1, p2.value, p2.proof.a1, p2.proof.a2)
        self.assertNotEqual(self._candidate_share(p1, e1, p2, e2), self.keyset.secret_shares[2])

    def test_same_ciphertext_different_epoch_no_share_leak(self) -> None:
        """Same ciphertext, two epochs: the epoch enters both nonce and challenge,
        so no two distinct challenges share a witness."""
        from ptr_v3.crypto import _proof_challenge

        p1, p2 = self.partial(3, self.ciphertext, epoch=1), self.partial(3, self.ciphertext, epoch=2)
        self.assertNotEqual(p1.proof.a1, p2.proof.a1)
        e1 = _proof_challenge(3, self.keyset.public_shares[2], self.ciphertext, 1, p1.value, p1.proof.a1, p1.proof.a2)
        e2 = _proof_challenge(3, self.keyset.public_shares[2], self.ciphertext, 2, p2.value, p2.proof.a1, p2.proof.a2)
        self.assertNotEqual(self._candidate_share(p1, e1, p2, e2), self.keyset.secret_shares[2])


class NetworkIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = NetworkIdentity.derive(2, "host2", 99)
        self.message = signing_message(
            operator_id=2,
            host_id="host2",
            order_id="order-1",
            buyer="buyer",
            resource="resource",
            epoch=1,
            partial_hash="a" * 64,
            proof_hash="b" * 64,
            nonce="c" * 32,
            runtime_source_digest="d" * 64,
        )

    def test_signature_verifies_and_is_deterministic(self) -> None:
        first = sign(self.identity, self.message)
        second = sign(self.identity, self.message)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertTrue(verify(self.identity.public_key, self.message, first))

    def test_another_operators_key_does_not_verify(self) -> None:
        other = NetworkIdentity.derive(4, "host2", 99)
        self.assertFalse(verify(other.public_key, self.message, sign(self.identity, self.message)))

    def test_host_relabelling_breaks_the_signature(self) -> None:
        signature = sign(self.identity, self.message)
        relabelled = signing_message(
            operator_id=2,
            host_id="host1",
            order_id="order-1",
            buyer="buyer",
            resource="resource",
            epoch=1,
            partial_hash="a" * 64,
            proof_hash="b" * 64,
            nonce="c" * 32,
            runtime_source_digest="d" * 64,
        )
        self.assertFalse(verify(self.identity.public_key, relabelled, signature))

    def test_runtime_source_digest_relabelling_breaks_the_signature(self) -> None:
        signature = sign(self.identity, self.message)
        relabelled = signing_message(
            operator_id=2,
            host_id="host2",
            order_id="order-1",
            buyer="buyer",
            resource="resource",
            epoch=1,
            partial_hash="a" * 64,
            proof_hash="b" * 64,
            nonce="c" * 32,
            runtime_source_digest="e" * 64,
        )
        self.assertFalse(verify(self.identity.public_key, relabelled, signature))

    def test_registry_reports_the_configured_host(self) -> None:
        registry = OperatorRegistry.build(
            [NetworkIdentity.derive(i, host, 99) for i, host in sorted(HOSTS.items())]
        )
        self.assertEqual(registry.host_of(2), "host2")
        self.assertEqual(registry.host_of(5), "host1")
        self.assertEqual(registry.public_key(2), NetworkIdentity.derive(2, "host2", 99).public_key)
        self.assertIsNone(registry.public_key(99))
        self.assertIsNone(registry.host_of(99))


class CertificateTests(unittest.TestCase):
    def test_theory_cover_is_the_q_smallest_floors(self) -> None:
        self.assertEqual(theory_cover(FLOORS, THRESHOLD), 1 + 2 + 3 + 4)

    def test_catalog_certificate_rejects_missing_floors(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete route catalog"):
            catalog_certificate([None, 14, 10, None, 12])

    def test_catalog_certificate_refuses_an_empty_catalog(self) -> None:
        with self.assertRaises(ValueError):
            catalog_certificate([None, None])

    def test_weighted_dp_matches_brute_force(self) -> None:
        weights = [3, 2, 2, 1, 1, 1, 1]
        prices = [5, 2, 3, 1, 1, 4, 6]
        for threshold in range(1, sum(weights) + 1):
            expected, _ = brute_force_weighted(weights, prices, threshold)
            self.assertEqual(weighted_dp(weights, prices, threshold), expected, threshold)


class BitmapTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        self.assertEqual(ids_of_bitmap(bitmap_of([1, 3, 5, 7])), [1, 3, 5, 7])

    def test_rejects_zero_based_ids(self) -> None:
        with self.assertRaises(ValueError):
            bitmap_of([0, 1])


def _witnesses(coalition=(1, 2, 3, 4), ledger: OrderLedger | None = None):
    prices = {i: FLOORS[i - 1] for i in range(1, SIZE + 1)}
    ledger = ledger or OrderLedger.open("order-1", "buyer", prices)
    hashes = []
    for operator_id in coalition:
        record = ledger.credit_before_release(operator_id, f"h{operator_id}" * 8, True, True)
        hashes.append(record.response_hash)
    ledger.mark_success()
    ledger.finalize_refund()

    bitmap = bitmap_of(coalition)
    aggregation = AggregationWitness(
        order_id="order-1",
        buyer="buyer",
        resource="resource",
        epoch=1,
        responder_bitmap=bitmap,
        operator_ids=tuple(coalition),
        host_ids=tuple(HOSTS[i] for i in coalition),
        partial_response_hashes=tuple(hashes),
        aggregate_valid=True,
        plaintext_hash="d" * 64,
    )
    refund_ids = tuple(r.return_id for r in ledger.returns if r.beneficiary == "buyer" and r.kind != "refund")
    entries = tuple(
        AllocationEntry(
            operator_id=operator_id,
            host_id=HOSTS[operator_id],
            responder_bitmap=bitmap,
            response_hash=hashes[position],
            debit_id=ledger.operator_debit_ids[operator_id],
            debit=FLOORS[operator_id - 1],
            refund_ids=refund_ids if position == 0 else (),
            refund=0,
            funding_ids=(),
            external_funding=0,
        )
        for position, operator_id in enumerate(coalition)
    )
    allocation = AllocationWitness("order-1", bitmap, entries)
    coverage = RouteCoverageEvidence(
        status="PROVED",
        scope_hash="e" * 64,
        route_catalog_hash="f" * 64,
        covered_routes=("paid_response",),
        excluded_routes=(),
        proof_kernel="test",
    )
    return ledger, aggregation, allocation, coverage


class AllocationWitnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger, self.aggregation, self.allocation, _ = _witnesses()
        self.floors = {i: FLOORS[i - 1] for i in (1, 2, 3, 4)}
        self.observed = self.ledger.named_buyer_net_outflow

    def check(self, allocation: AllocationWitness):
        return verify_allocation_witness(self.aggregation, allocation, self.floors, self.observed)

    def test_well_formed_witness_passes(self) -> None:
        result = self.check(self.allocation)
        self.assertTrue(result.ok, result.failures)
        self.assertEqual(self.allocation.total_allocated, 10)

    def test_reused_debit_id_is_caught(self) -> None:
        entries = list(self.allocation.entries)
        entries[1] = AllocationEntry(**{**entries[1].__dict__, "debit_id": entries[0].debit_id})
        result = self.check(AllocationWitness("order-1", self.allocation.responder_bitmap, tuple(entries)))
        self.assertFalse(result.ok)
        self.assertTrue(any("allocated more than once" in f for f in result.failures))

    def test_foreign_bitmap_is_caught(self) -> None:
        entries = list(self.allocation.entries)
        entries[0] = AllocationEntry(**{**entries[0].__dict__, "responder_bitmap": "0xff"})
        result = self.check(AllocationWitness("order-1", self.allocation.responder_bitmap, tuple(entries)))
        self.assertFalse(result.ok)
        self.assertTrue(any("foreign responder bitmap" in f for f in result.failures))

    def test_relabelled_host_is_caught(self) -> None:
        entries = list(self.allocation.entries)
        entries[1] = AllocationEntry(**{**entries[1].__dict__, "host_id": "host1"})
        result = self.check(AllocationWitness("order-1", self.allocation.responder_bitmap, tuple(entries)))
        self.assertFalse(result.ok)
        self.assertTrue(any("host differs" in f for f in result.failures))

    def test_allocation_below_a_floor_is_caught(self) -> None:
        entries = list(self.allocation.entries)
        entries[3] = AllocationEntry(**{**entries[3].__dict__, "debit": 1})
        result = self.check(AllocationWitness("order-1", self.allocation.responder_bitmap, tuple(entries)))
        self.assertFalse(result.ok)
        self.assertTrue(any("below its floor" in f for f in result.failures))

    def test_allocating_more_than_was_spent_is_caught(self) -> None:
        result = verify_allocation_witness(self.aggregation, self.allocation, self.floors, observed_outflow=9)
        self.assertFalse(result.ok)
        self.assertTrue(any("exceeds the realized outflow" in f for f in result.failures))


class GateTests(unittest.TestCase):
    def build(self, ledger, aggregation, allocation, coverage, consumer="buyer", gateway=True):
        view = ExecutionView(
            order_id="order-1",
            buyer="buyer",
            consumer=consumer,
            threshold=THRESHOLD,
            counted_operator_ids=list(aggregation.operator_ids),
            aggregate_valid=aggregation.aggregate_valid,
            gateway_accepted=gateway,
            ledger=ledger,
        )
        return evaluate(view, aggregation, allocation, coverage, FLOORS)

    def test_clean_execution_certifies_at_the_ledger_derived_floor(self) -> None:
        report = self.build(*_witnesses())
        self.assertEqual(report.status, CERTIFIED)
        self.assertEqual(report.execution_floor, 10)
        self.assertEqual(report.observed_outflow, 10)

    def test_wrong_consumer_refutes_b1_and_makes_b3_not_applicable(self) -> None:
        report = self.build(*_witnesses(), consumer="mallory", gateway=False)
        self.assertEqual(report.gates["B1"].status, FAIL_COUNTEREXAMPLE)
        self.assertEqual(report.gates["B3"].status, NOT_APPLICABLE)
        self.assertEqual(report.status, REFUTED)

    def test_sponsor_funding_refutes_b2_only(self) -> None:
        prices = {i: FLOORS[i - 1] for i in range(1, SIZE + 1)}
        ledger = OrderLedger.open("order-1", "buyer", prices, source="sponsor")
        report = self.build(*_witnesses(ledger=ledger))
        self.assertEqual(report.gates["B2"].status, FAIL_COUNTEREXAMPLE)
        self.assertEqual(report.gates["B1"].status, "PASS")
        self.assertEqual(report.status, REFUTED)

    def test_missing_ordering_evidence_is_unknown_not_refuted(self) -> None:
        ledger, aggregation, allocation, coverage = _witnesses()
        for record in ledger.responses:
            record.ordering_evidence = False
        report = self.build(ledger, aggregation, allocation, coverage)
        self.assertEqual(report.gates["B3"].status, FAIL_CLOSED_MISSING_EVIDENCE)
        self.assertEqual(report.status, UNKNOWN)

    def test_unaccounted_return_refutes_b4_only(self) -> None:
        ledger, aggregation, allocation, coverage = _witnesses()
        ledger.add_reimbursement(3, accounted=False)
        report = self.build(ledger, aggregation, allocation, coverage)
        self.assertEqual(report.gates["B4"].status, FAIL_COUNTEREXAMPLE)
        self.assertEqual(report.gates["B1"].status, "PASS")
        self.assertEqual(report.status, REFUTED)

    def test_missing_coverage_proof_is_unknown_not_refuted(self) -> None:
        ledger, aggregation, allocation, coverage = _witnesses()
        report = self.build(
            ledger, aggregation, allocation, RouteCoverageEvidence(**{**coverage.__dict__, "status": "UNKNOWN"})
        )
        self.assertEqual(report.gates["B5"].status, FAIL_CLOSED_MISSING_EVIDENCE)
        self.assertEqual(report.status, UNKNOWN)
        self.assertEqual(report.execution_floor, 0)

    def test_certificate_is_not_the_closed_form(self) -> None:
        """A failing allocation must erase the floor, not fall back to theory."""
        ledger, aggregation, allocation, coverage = _witnesses()
        entries = list(allocation.entries)
        entries[0] = AllocationEntry(**{**entries[0].__dict__, "debit": 0})
        broken = AllocationWitness("order-1", allocation.responder_bitmap, tuple(entries))
        report = self.build(ledger, aggregation, broken, coverage)
        self.assertEqual(report.execution_floor, 0)
        self.assertEqual(report.status, UNKNOWN)


class SeparationWitnessTests(unittest.TestCase):
    LOCAL = "local-digest"
    REMOTE = "remote-digest"

    def probes(self, *, loopback: bool, peer_equals_local: bool = False):
        out = []
        for operator_id, host in sorted(HOSTS.items()):
            remote = host != "host1"
            out.append(
                {
                    "operator_id": operator_id,
                    "configured_host_id": host,
                    "observed_peer_address": "127.0.0.1" if (loopback or not remote) else "192.0.2.9",
                    "observed_local_address": "127.0.0.1" if (loopback or not remote) else "192.0.2.8",
                    "peer_is_loopback": (loopback or not remote),
                    "peer_equals_local": peer_equals_local and remote,
                }
            )
        return out

    def health(self, remote_digest: str):
        return {
            operator_id: {"machine_digest": self.LOCAL if host == "host1" else remote_digest}
            for operator_id, host in HOSTS.items()
        }

    def build(self, probes, health):
        return build_separation_witness("host1", self.LOCAL, probes, health, HOSTS)

    def test_two_machines_pass(self) -> None:
        witness = self.build(self.probes(loopback=False), self.health(self.REMOTE))
        self.assertEqual(witness.status, "PASS")
        self.assertTrue(witness.passed)
        self.assertEqual(witness.distinct_machines_observed, 2)

    def test_loopback_rehearsal_is_a_counterexample(self) -> None:
        witness = self.build(self.probes(loopback=True), self.health(self.LOCAL))
        self.assertEqual(witness.status, FAIL_COUNTEREXAMPLE)
        self.assertFalse(witness.passed)
        self.assertEqual(witness.distinct_machines_observed, 1)

    def test_matching_fingerprint_defeats_a_non_local_address(self) -> None:
        """Distinct addresses are not enough if both ends are the same box."""
        witness = self.build(self.probes(loopback=False), self.health(self.LOCAL))
        self.assertEqual(witness.status, FAIL_COUNTEREXAMPLE)
        self.assertIn("own fingerprint", witness.reason)

    def test_self_addressed_peer_is_a_counterexample(self) -> None:
        witness = self.build(
            self.probes(loopback=False, peer_equals_local=True), self.health(self.REMOTE)
        )
        self.assertEqual(witness.status, FAIL_COUNTEREXAMPLE)
        self.assertIn("own address", witness.reason)

    def test_missing_fingerprint_fails_closed(self) -> None:
        """An older operator build reports no digest; the address alone is not enough."""
        health = self.health(self.REMOTE)
        health[6] = {}
        witness = self.build(self.probes(loopback=False), health)
        self.assertEqual(witness.status, FAIL_CLOSED_MISSING_EVIDENCE)
        self.assertIn("no machine fingerprint", witness.reason)

    def test_missing_probe_fails_closed(self) -> None:
        probes = [p for p in self.probes(loopback=False) if p["operator_id"] != 7]
        witness = self.build(probes, self.health(self.REMOTE))
        self.assertEqual(witness.status, FAIL_CLOSED_MISSING_EVIDENCE)
        self.assertIn("[7]", witness.reason)

    def test_canonical_view_carries_no_addresses(self) -> None:
        witness = self.build(self.probes(loopback=False), self.health(self.REMOTE))
        rendered = repr(witness.to_dict())
        self.assertNotIn("192.168", rendered)
        self.assertNotIn("127.0.0.1", rendered)
        self.assertNotIn(self.LOCAL, rendered)
        self.assertIn("192.0.2", repr(witness.to_metadata_dict()))


META = {
    "committee_size": SIZE,
    "threshold": THRESHOLD,
    "response_floors": list(FLOORS),
    "buyer": "b",
    "resource": "r",
    "epoch": 1,
    "operator_hosts": {str(k): v for k, v in HOSTS.items()},
}


class DealerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dealt = deal(META, seed=11, network_seed=22)

    def test_public_bundle_has_no_secret(self) -> None:
        blob = __import__("json").dumps(self.dealt.public_bundle)
        for field in ("seed", "network_seed", "secret_share", "secret_shares", "network_secret_key"):
            self.assertNotIn(field, self.dealt.public_bundle)
        self.assertNotIn("secret", blob)

    def test_every_operator_gets_one_secret(self) -> None:
        self.assertEqual(sorted(self.dealt.secrets_by_operator), list(range(1, SIZE + 1)))
        for operator_id, secret in self.dealt.secrets_by_operator.items():
            self.assertEqual(secret["operator_id"], operator_id)
            self.assertIn("secret_share", secret)
            self.assertIn("network_secret_key", secret)

    def test_public_shares_match_secret_shares(self) -> None:
        from ptr_v3.crypto import G, P

        for operator_id, secret in self.dealt.secrets_by_operator.items():
            share = int(secret["secret_share"], 16)
            expected = pow(G, share, P)
            got = int(self.dealt.public_bundle["public_shares"][str(operator_id)], 16)
            self.assertEqual(expected, got)

    def test_secret_share_reproduces_a_verifiable_partial(self) -> None:
        public_key = int(self.dealt.public_bundle["public_key"], 16)
        ciphertext = encrypt_capability(public_key, "b", "r", "order-1", seed=3)
        for operator_id in (2, 4, 6, 7):
            secret = self.dealt.secrets_by_operator[operator_id]
            share = int(secret["secret_share"], 16)
            public_share = int(secret["public_share"], 16)
            response = create_partial(operator_id, share, public_share, ciphertext, 1)
            self.assertTrue(verify_partial(public_share, ciphertext, response, 1))

    def test_from_secret_and_from_public_agree(self) -> None:
        secret = self.dealt.secrets_by_operator[2]
        identity = NetworkIdentity.from_secret(2, "host2", int(secret["network_secret_key"], 16))
        self.assertEqual(hex(identity.public_key), self.dealt.public_bundle["network_public_keys"]["2"])
        registry = OperatorRegistry.from_public(
            {int(k): v for k, v in META["operator_hosts"].items()},
            {int(k): int(v, 16) for k, v in self.dealt.public_bundle["network_public_keys"].items()},
        )
        self.assertEqual(registry.public_key(2), identity.public_key)
        self.assertEqual(registry.host_of(2), "host2")


class HostLocalSecretFilePlacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(__import__("tempfile").mkdtemp())
        self.dealt = deal(META, seed=11, network_seed=22)
        self.public = self.tmp / "committee.public.v3.json"
        write_dealt(
            self.dealt,
            public_path=self.public,
            secret_dir=self.tmp / "secrets" / "host1",
            operators=[1, 3, 5],
        )

    def tearDown(self) -> None:
        __import__("shutil").rmtree(self.tmp, ignore_errors=True)

    def witness(self):
        return build_host_local_secret_file_placement_witness("host1", self.tmp / "secrets" / "host1", self.public, dict(HOSTS))

    def test_clean_host1_passes(self) -> None:
        w = self.witness()
        self.assertEqual(w.status, "PASS")
        self.assertEqual(w.secret_files_present, (1, 3, 5))

    def test_foreign_secret_is_a_counterexample(self) -> None:
        write_dealt(self.dealt, public_path=self.public, secret_dir=self.tmp / "secrets" / "host1", operators=[2])
        w = self.witness()
        self.assertEqual(w.status, "FAIL_COUNTEREXAMPLE")
        self.assertIn("2", w.reason)

    def test_seed_in_public_bundle_is_a_counterexample(self) -> None:
        import json as _json

        bundle = _json.loads(self.public.read_text())
        bundle["seed"] = 123
        self.public.write_text(_json.dumps(bundle))
        self.assertEqual(self.witness().status, "FAIL_COUNTEREXAMPLE")

    def test_missing_own_secret_fails_closed(self) -> None:
        (self.tmp / "secrets" / "host1" / "operator-3.secret.json").unlink()
        self.assertEqual(self.witness().status, "FAIL_CLOSED_MISSING_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
