from __future__ import annotations

from dataclasses import dataclass
import random
import secrets
from typing import Iterable, Sequence

from .utils import hash_to_int, int_to_bytes

# RFC 3526 MODP Group 14 safe prime. We work in its quadratic-residue subgroup.
_P_HEX = """
FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1
29024E088A67CC74020BBEA63B139B22514A08798E3404DD
EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245
E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED
EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D
C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F
83655D23DCA3AD961C62F356208552BB9ED529077096966D
670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B
E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9
DE2BCBF6955817183995497CEA956AE515D2261898FA0510
15728E5A8AACAA68FFFFFFFFFFFFFFFF
""".replace("\n", "")

P = int(_P_HEX, 16)
Q = (P - 1) // 2
G = 4  # generator of the order-Q quadratic-residue subgroup

if pow(G, Q, P) != 1 or G == 1:
    raise RuntimeError("invalid group parameters")


def mod_inv(value: int, modulus: int) -> int:
    value %= modulus
    if value == 0:
        raise ZeroDivisionError("inverse of zero")
    return pow(value, -1, modulus)


def lagrange_at_zero(index: int, indices: Sequence[int]) -> int:
    if index not in indices:
        raise ValueError("index missing")
    numerator = 1
    denominator = 1
    for other in indices:
        if other == index:
            continue
        numerator = (numerator * (-other)) % Q
        denominator = (denominator * (index - other)) % Q
    return numerator * mod_inv(denominator, Q) % Q


class ScalarRng:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed) if seed is not None else None

    def scalar(self) -> int:
        if self._rng is None:
            return secrets.randbelow(Q - 1) + 1
        while True:
            value = self._rng.getrandbits(Q.bit_length()) % Q
            if value != 0:
                return value

    def bytes(self, length: int) -> bytes:
        if self._rng is None:
            return secrets.token_bytes(length)
        return bytes(self._rng.randrange(0, 256) for _ in range(length))


@dataclass(frozen=True)
class Ciphertext:
    c1: int
    c2: int
    buyer: str
    resource: str
    order_id: str
    expected_plaintext: int

    def context_bytes(self) -> bytes:
        return b"|".join(
            [
                self.buyer.encode(),
                self.resource.encode(),
                self.order_id.encode(),
                int_to_bytes(self.c1),
                int_to_bytes(self.c2),
            ]
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "c1": hex(self.c1),
            "c2": hex(self.c2),
            "buyer": self.buyer,
            "resource": self.resource,
            "order_id": self.order_id,
            "expected_plaintext": hex(self.expected_plaintext),
        }

    @staticmethod
    def from_dict(value: dict[str, str]) -> "Ciphertext":
        return Ciphertext(
            c1=int(value["c1"], 16),
            c2=int(value["c2"], 16),
            buyer=value["buyer"],
            resource=value["resource"],
            order_id=value["order_id"],
            expected_plaintext=int(value["expected_plaintext"], 16),
        )


@dataclass(frozen=True)
class ChaumPedersenProof:
    a1: int
    a2: int
    z: int

    def to_dict(self) -> dict[str, str]:
        return {"a1": hex(self.a1), "a2": hex(self.a2), "z": hex(self.z)}

    @staticmethod
    def from_dict(value: dict[str, str]) -> "ChaumPedersenProof":
        return ChaumPedersenProof(a1=int(value["a1"], 16), a2=int(value["a2"], 16), z=int(value["z"], 16))


@dataclass(frozen=True)
class PartialDecryption:
    operator_id: int
    value: int
    proof: ChaumPedersenProof

    def to_dict(self) -> dict[str, object]:
        return {"operator_id": self.operator_id, "value": hex(self.value), "proof": self.proof.to_dict()}

    @staticmethod
    def from_dict(value: dict[str, object]) -> "PartialDecryption":
        return PartialDecryption(
            operator_id=int(value["operator_id"]),
            value=int(str(value["value"]), 16),
            proof=ChaumPedersenProof.from_dict(dict(value["proof"])),
        )


@dataclass(frozen=True)
class ThresholdKeySet:
    n: int
    threshold: int
    public_key: int
    secret_shares: tuple[int, ...]
    public_shares: tuple[int, ...]

    @staticmethod
    def generate(n: int, threshold: int, seed: int | None = None) -> "ThresholdKeySet":
        if not 1 <= threshold <= n:
            raise ValueError("invalid threshold")
        rng = ScalarRng(seed)
        coefficients = [rng.scalar() for _ in range(threshold)]
        secret = coefficients[0]

        def eval_poly(x: int) -> int:
            acc = 0
            power = 1
            for coefficient in coefficients:
                acc = (acc + coefficient * power) % Q
                power = power * x % Q
            return acc

        shares = tuple(eval_poly(i) for i in range(1, n + 1))
        public_shares = tuple(pow(G, share, P) for share in shares)
        return ThresholdKeySet(
            n=n,
            threshold=threshold,
            public_key=pow(G, secret, P),
            secret_shares=shares,
            public_shares=public_shares,
        )


def encrypt_capability(
    public_key: int,
    buyer: str,
    resource: str,
    order_id: str,
    seed: int | None = None,
) -> Ciphertext:
    rng = ScalarRng(seed)
    token_material = rng.bytes(32)
    token_scalar = hash_to_int(Q, b"PTR-CAPABILITY", buyer.encode(), resource.encode(), order_id.encode(), token_material)
    token_scalar = token_scalar or 1
    plaintext = pow(G, token_scalar, P)
    nonce = rng.scalar()
    c1 = pow(G, nonce, P)
    c2 = plaintext * pow(public_key, nonce, P) % P
    return Ciphertext(c1=c1, c2=c2, buyer=buyer, resource=resource, order_id=order_id, expected_plaintext=plaintext)


def _proof_challenge(
    operator_id: int,
    public_share: int,
    ciphertext: Ciphertext,
    partial: int,
    a1: int,
    a2: int,
) -> int:
    return hash_to_int(
        Q,
        b"PTR-CP-PROOF-v1",
        operator_id.to_bytes(4, "big"),
        int_to_bytes(G),
        int_to_bytes(public_share),
        int_to_bytes(ciphertext.c1),
        int_to_bytes(partial),
        int_to_bytes(a1),
        int_to_bytes(a2),
        ciphertext.context_bytes(),
    )


def create_partial(
    operator_id: int,
    share: int,
    public_share: int,
    ciphertext: Ciphertext,
    seed: int | None = None,
) -> PartialDecryption:
    if operator_id <= 0:
        raise ValueError("operator_id must be positive")
    partial = pow(ciphertext.c1, share, P)
    rng = ScalarRng(seed)
    witness = rng.scalar()
    a1 = pow(G, witness, P)
    a2 = pow(ciphertext.c1, witness, P)
    challenge = _proof_challenge(operator_id, public_share, ciphertext, partial, a1, a2)
    z = (witness + challenge * share) % Q
    return PartialDecryption(operator_id=operator_id, value=partial, proof=ChaumPedersenProof(a1=a1, a2=a2, z=z))


def verify_partial(public_share: int, ciphertext: Ciphertext, response: PartialDecryption) -> bool:
    if not (1 < response.value < P):
        return False
    proof = response.proof
    challenge = _proof_challenge(
        response.operator_id,
        public_share,
        ciphertext,
        response.value,
        proof.a1,
        proof.a2,
    )
    lhs1 = pow(G, proof.z, P)
    rhs1 = proof.a1 * pow(public_share, challenge, P) % P
    lhs2 = pow(ciphertext.c1, proof.z, P)
    rhs2 = proof.a2 * pow(response.value, challenge, P) % P
    return lhs1 == rhs1 and lhs2 == rhs2


def combine_partials(ciphertext: Ciphertext, responses: Sequence[PartialDecryption], threshold: int) -> int:
    if len(responses) < threshold:
        raise ValueError("not enough partial decryptions")
    selected = list(responses[:threshold])
    indices = [response.operator_id for response in selected]
    if len(set(indices)) != len(indices):
        raise ValueError("duplicate operator")
    combined = 1
    for response in selected:
        coefficient = lagrange_at_zero(response.operator_id, indices)
        combined = combined * pow(response.value, coefficient, P) % P
    plaintext = ciphertext.c2 * mod_inv(combined, P) % P
    return plaintext


def verify_threshold_result(ciphertext: Ciphertext, plaintext: int) -> bool:
    return plaintext == ciphertext.expected_plaintext
