"""Per-operator network identity, separate from the threshold share.

An operator proves two different things about a response. The Chaum--Pedersen
proof shows the partial decryption really was computed with the share matching
the registered public share. The Schnorr signature here shows *which operator on
which host* sent it, over the whole response context, so host 1 cannot relabel
operator 2's answer as operator 4's, and a captured response cannot be replayed
into a different order.

Nonces are derived deterministically from the signing key and the message. A
random nonce would make the canonical result differ on every run, which would
destroy the replay check that the whole artifact rests on; deterministic
derivation is also the safer construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .crypto import G, P, Q
from .utils import canonical_json_bytes, hash_to_int, int_to_bytes, sha256_hex


@dataclass(frozen=True)
class SchnorrSignature:
    r: int
    s: int

    def to_dict(self) -> dict[str, str]:
        return {"r": hex(self.r), "s": hex(self.s)}

    @staticmethod
    def from_dict(value: Mapping[str, str]) -> "SchnorrSignature":
        return SchnorrSignature(r=int(value["r"], 16), s=int(value["s"], 16))


@dataclass(frozen=True)
class NetworkIdentity:
    operator_id: int
    host_id: str
    secret_key: int
    public_key: int

    @staticmethod
    def derive(operator_id: int, host_id: str, seed: int) -> "NetworkIdentity":
        """Dealer-only: derive an identity from the one-time network seed.

        This is called during key setup, on the dealer, to mint every operator's
        network key. It is never called at run time, because a host that could
        call it would hold the seed and could forge any operator's signature.
        Hosts load their own key with :meth:`from_secret` instead.
        """
        secret = hash_to_int(
            Q,
            b"PTR-V3-NETWORK-KEY",
            int_to_bytes(seed),
            operator_id.to_bytes(4, "big"),
            host_id.encode(),
        )
        secret = secret or 1
        return NetworkIdentity.from_secret(operator_id, host_id, secret)

    @staticmethod
    def from_secret(operator_id: int, host_id: str, secret_key: int) -> "NetworkIdentity":
        if not 1 <= secret_key < Q:
            raise ValueError("network secret key out of range")
        return NetworkIdentity(
            operator_id=operator_id,
            host_id=host_id,
            secret_key=secret_key,
            public_key=pow(G, secret_key, P),
        )

    def public_record(self) -> dict[str, object]:
        return {
            "operator_id": self.operator_id,
            "host_id": self.host_id,
            "network_public_key": hex(self.public_key),
        }


def signing_message(
    *,
    operator_id: int,
    host_id: str,
    order_id: str,
    buyer: str,
    resource: str,
    epoch: int,
    partial_hash: str,
    proof_hash: str,
    nonce: str,
    runtime_source_digest: str,
) -> bytes:
    """The exact bytes an operator signs.

    Every field the coordinator later checks is inside, so a signature cannot be
    lifted from one order, buyer, resource, epoch or operator to another.
    """
    return canonical_json_bytes(
        {
            "protocol_version": PROTOCOL_VERSION,
            "operator_id": operator_id,
            "host_id": host_id,
            "order_id": order_id,
            "buyer": buyer,
            "resource": resource,
            "epoch": epoch,
            "partial_hash": partial_hash,
            "proof_hash": proof_hash,
            "nonce": nonce,
            "runtime_source_digest": runtime_source_digest,
        }
    )


PROTOCOL_VERSION = "ptr-two-host/v5"


def sign(identity: NetworkIdentity, message: bytes) -> SchnorrSignature:
    k = hash_to_int(Q, b"PTR-V5-SCHNORR-NONCE", int_to_bytes(identity.secret_key), message)
    k = k or 1
    r = pow(G, k, P)
    e = hash_to_int(Q, b"PTR-V3-SCHNORR-CHALLENGE", int_to_bytes(r), int_to_bytes(identity.public_key), message)
    s = (k + e * identity.secret_key) % Q
    return SchnorrSignature(r=r, s=s)


def verify(public_key: int, message: bytes, signature: SchnorrSignature) -> bool:
    if not (1 < signature.r < P) or not (0 <= signature.s < Q):
        return False
    e = hash_to_int(Q, b"PTR-V3-SCHNORR-CHALLENGE", int_to_bytes(signature.r), int_to_bytes(public_key), message)
    return pow(G, signature.s, P) == signature.r * pow(public_key, e, P) % P


@dataclass(frozen=True)
class OperatorRegistry:
    """The coordinator's view of who may answer, and from where."""

    entries: tuple[dict[str, object], ...]

    @staticmethod
    def build(identities: Sequence[NetworkIdentity]) -> "OperatorRegistry":
        return OperatorRegistry(tuple(identity.public_record() for identity in identities))

    @staticmethod
    def from_public(
        operator_hosts: Mapping[int, str], network_public_keys: Mapping[int, int]
    ) -> "OperatorRegistry":
        """Build the coordinator's registry from public data only.

        The coordinator holds no secret and no seed, so it cannot mint these
        keys; it can only recognise the public keys it was handed. This is what
        makes ``REMOTE_OPERATOR_IDENTITY`` mean something: a matching signature
        could only have come from a key host 1 does not possess.
        """

        entries = tuple(
            {
                "operator_id": operator_id,
                "host_id": operator_hosts[operator_id],
                "network_public_key": hex(network_public_keys[operator_id]),
            }
            for operator_id in sorted(operator_hosts)
        )
        return OperatorRegistry(entries)

    def public_key(self, operator_id: int) -> int | None:
        for entry in self.entries:
            if entry["operator_id"] == operator_id:
                return int(str(entry["network_public_key"]), 16)
        return None

    def host_of(self, operator_id: int) -> str | None:
        for entry in self.entries:
            if entry["operator_id"] == operator_id:
                return str(entry["host_id"])
        return None

    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(list(self.entries)))

    def to_dict(self) -> dict[str, object]:
        return {"type": "operator_registry", "entries": list(self.entries), "digest": self.digest()}

