from __future__ import annotations

import unittest

from ptr_v3.crypto import (
    Ciphertext,
    ThresholdKeySet,
    combine_partials,
    create_partial,
    encrypt_capability,
    verify_threshold_result,
)


class PublicCiphertextBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.keys = ThresholdKeySet.generate(7, 4, seed=47)

    def test_public_ciphertext_contains_commitment_not_plaintext(self) -> None:
        ciphertext = encrypt_capability(
            self.keys.public_key,
            "buyer",
            "resource",
            "order",
            seed=53,
        )
        encoded = ciphertext.to_dict()
        self.assertEqual(
            set(encoded),
            {"c1", "c2", "buyer", "resource", "order_id", "plaintext_commitment"},
        )
        self.assertNotIn("expected_plaintext", encoded)
        self.assertNotIn("plaintext", encoded)
        self.assertNotIn("seed", encoded)
        self.assertEqual(Ciphertext.from_dict(encoded), ciphertext)

    def test_commitment_accepts_only_threshold_reconstruction(self) -> None:
        ciphertext = encrypt_capability(
            self.keys.public_key,
            "buyer",
            "resource",
            "order",
            seed=59,
        )
        partials = [
            create_partial(
                operator_id,
                self.keys.secret_shares[operator_id - 1],
                self.keys.public_shares[operator_id - 1],
                ciphertext,
                1,
            )
            for operator_id in (1, 2, 3, 4)
        ]
        plaintext = combine_partials(ciphertext, partials, 4)
        self.assertTrue(verify_threshold_result(ciphertext, plaintext))
        self.assertFalse(verify_threshold_result(ciphertext, plaintext + 1))

    def test_commitment_is_bound_to_context(self) -> None:
        base = encrypt_capability(
            self.keys.public_key,
            "buyer",
            "resource",
            "order",
            seed=61,
        )
        partials = [
            create_partial(
                operator_id,
                self.keys.secret_shares[operator_id - 1],
                self.keys.public_shares[operator_id - 1],
                base,
                1,
            )
            for operator_id in (1, 2, 3, 4)
        ]
        plaintext = combine_partials(base, partials, 4)
        relabelled = Ciphertext(
            base.c1,
            base.c2,
            base.buyer,
            base.resource,
            "different-order",
            base.plaintext_commitment,
        )
        self.assertFalse(verify_threshold_result(relabelled, plaintext))


if __name__ == "__main__":
    unittest.main()