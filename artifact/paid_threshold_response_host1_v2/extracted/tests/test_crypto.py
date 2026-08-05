from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_exp.crypto import ThresholdKeySet, combine_partials, create_partial, encrypt_capability, verify_partial, verify_threshold_result


class CryptoTests(unittest.TestCase):
    def test_threshold_decryption_and_proofs(self) -> None:
        keys = ThresholdKeySet.generate(7, 4, seed=1)
        ciphertext = encrypt_capability(keys.public_key, "buyer", "resource", "order", seed=2)
        responses = []
        for operator_id in [1, 3, 5, 7]:
            response = create_partial(
                operator_id,
                keys.secret_shares[operator_id - 1],
                keys.public_shares[operator_id - 1],
                ciphertext,
                seed=100 + operator_id,
            )
            self.assertTrue(verify_partial(keys.public_shares[operator_id - 1], ciphertext, response))
            responses.append(response)
        plaintext = combine_partials(ciphertext, responses, 4)
        self.assertTrue(verify_threshold_result(ciphertext, plaintext))

    def test_wrong_public_share_rejects_proof(self) -> None:
        keys = ThresholdKeySet.generate(5, 3, seed=4)
        ciphertext = encrypt_capability(keys.public_key, "buyer", "resource", "order", seed=5)
        response = create_partial(1, keys.secret_shares[0], keys.public_shares[0], ciphertext, seed=6)
        self.assertFalse(verify_partial(keys.public_shares[1], ciphertext, response))


if __name__ == "__main__":
    unittest.main()
