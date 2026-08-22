"""Host 1's coordinator: request responses, verify them, refuse the rest.

Seven independent checks run on every response before it may be counted. Five
of them exist because the coordinator and the operator are on different
machines: without them host 1 could relabel a remote answer, reuse an old one,
or quietly substitute a local operator for an unreachable remote one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import json
import socket
import time
from typing import Mapping, Sequence
import urllib.error
import urllib.request

from .crypto import Ciphertext, PartialDecryption, verify_partial
from .network_identity import (
    OperatorRegistry,
    PROTOCOL_VERSION,
    SchnorrSignature,
    signing_message,
    verify as verify_signature,
)
from .utils import canonical_json_bytes, sha256_hex


@dataclass(frozen=True)
class OperatorEndpoint:
    operator_id: int
    host_id: str
    address: str
    port: int

    @property
    def url(self) -> str:
        return f"http://{self.address}:{self.port}"


@dataclass
class VerifiedResponse:
    operator_id: int
    host_id: str
    partial: PartialDecryption
    partial_hash: str
    proof_hash: str
    response_hash: str
    nonce: str
    runtime_source_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "operator_id": self.operator_id,
            "host_id": self.host_id,
            "partial_hash": self.partial_hash,
            "proof_hash": self.proof_hash,
            "response_hash": self.response_hash,
            "runtime_source_digest": self.runtime_source_digest,
        }


@dataclass
class RejectedResponse:
    operator_id: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"operator_id": self.operator_id, "reason": self.reason}


@dataclass
class Coordinator:
    registry: OperatorRegistry
    endpoints: Mapping[int, OperatorEndpoint]
    public_shares: Sequence[int]
    expected_runtime_source_digest: str
    timeout_s: float = 5.0
    seen_nonces: set[str] = field(default_factory=set)
    transcript: list[dict[str, object]] = field(default_factory=list)

    # --- transport -------------------------------------------------------
    def _post(self, endpoint: OperatorEndpoint, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{endpoint.url}/respond",
            data=json.dumps(payload, sort_keys=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as handle:
            return json.loads(handle.read())

    def health(self, operator_id: int) -> dict[str, object] | None:
        endpoint = self.endpoints.get(operator_id)
        if endpoint is None:
            return None
        try:
            with urllib.request.urlopen(f"{endpoint.url}/health", timeout=self.timeout_s) as handle:
                return json.loads(handle.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def probe_endpoint(self, operator_id: int) -> dict[str, object] | None:
        """Observe where a connection to this operator actually lands.

        The configured address is a claim; ``getpeername`` on a live connection
        is what the kernel resolved it to, and ``getsockname`` is the local
        address host 1 answered from. Both go into the separation witness.
        """

        endpoint = self.endpoints.get(operator_id)
        if endpoint is None:
            return None
        try:
            with socket.create_connection((endpoint.address, endpoint.port), timeout=self.timeout_s) as sock:
                peer = sock.getpeername()[0]
                local = sock.getsockname()[0]
        except OSError:
            return None
        peer_ip = ipaddress.ip_address(peer)
        return {
            "operator_id": operator_id,
            "configured_host_id": endpoint.host_id,
            "observed_peer_address": peer,
            "observed_local_address": local,
            "peer_is_loopback": peer_ip.is_loopback,
            "peer_equals_local": peer == local,
        }

    # --- verification ----------------------------------------------------
    def _verify(
        self,
        payload: Mapping[str, object],
        *,
        operator_id: int,
        order_id: str,
        buyer: str,
        resource: str,
        epoch: int,
        nonce: str,
        ciphertext: Ciphertext,
        tamper: str | None = None,
    ) -> VerifiedResponse | RejectedResponse:
        payload = dict(payload)
        if tamper == "partial":
            payload["partial_decryption"] = hex((int(str(payload["partial_decryption"]), 16) + 1))
        elif tamper == "proof":
            proof = dict(payload["chaum_pedersen_proof"])  # type: ignore[arg-type]
            proof["z"] = hex(int(proof["z"], 16) + 1)
            payload["chaum_pedersen_proof"] = proof
        elif tamper == "buyer":
            payload["buyer"] = "mallory"
        elif tamper == "order":
            payload["order_id"] = f"{order_id}-tampered"
        elif tamper == "epoch":
            payload["epoch"] = int(payload["epoch"]) + 1
        elif tamper == "impersonate":
            payload["operator_id"] = operator_id + 2

        claimed = int(payload["operator_id"])

        # 1. the response answers the order that was asked
        if (
            payload.get("protocol_version") != PROTOCOL_VERSION
            or payload.get("order_id") != order_id
            or payload.get("buyer") != buyer
            or payload.get("resource") != resource
            or int(payload.get("epoch", -1)) != epoch
            or payload.get("runtime_source_digest") != self.expected_runtime_source_digest
        ):
            return RejectedResponse(claimed, "context mismatch: order, buyer, resource, epoch or runtime source")

        # 2. the nonce has not been used before in this session
        if payload.get("nonce") != nonce:
            return RejectedResponse(claimed, "nonce echoed back does not match the request")
        if nonce in self.seen_nonces:
            return RejectedResponse(claimed, "replayed nonce")

        # 3. the operator is registered, and on the host the config expects
        public_key = self.registry.public_key(claimed)
        expected_host = self.registry.host_of(claimed)
        if public_key is None or expected_host is None:
            return RejectedResponse(claimed, "operator is not in the registry")
        if payload.get("host_id") != expected_host:
            return RejectedResponse(claimed, f"operator claims host {payload.get('host_id')}, registry says {expected_host}")

        # 4. the network signature covers the whole context
        partial_hash = str(payload["partial_hash"])
        proof_hash = str(payload["proof_hash"])
        message = signing_message(
            operator_id=claimed,
            host_id=str(payload["host_id"]),
            order_id=order_id,
            buyer=buyer,
            resource=resource,
            epoch=epoch,
            partial_hash=partial_hash,
            proof_hash=proof_hash,
            nonce=nonce,
            runtime_source_digest=self.expected_runtime_source_digest,
        )
        signature = SchnorrSignature.from_dict(payload["operator_signature"])  # type: ignore[arg-type]
        if not verify_signature(public_key, message, signature):
            return RejectedResponse(claimed, "network signature does not verify")

        # 5. the hashes in the envelope match the material they name
        partial_value = int(str(payload["partial_decryption"]), 16)
        proof_dict = dict(payload["chaum_pedersen_proof"])  # type: ignore[arg-type]
        if sha256_hex(canonical_json_bytes({"value": hex(partial_value)})) != partial_hash:
            return RejectedResponse(claimed, "partial does not match its declared hash")
        if sha256_hex(canonical_json_bytes(proof_dict)) != proof_hash:
            return RejectedResponse(claimed, "proof does not match its declared hash")

        # 6. the partial really was produced with the registered share
        partial = PartialDecryption.from_dict(
            {"operator_id": claimed, "value": hex(partial_value), "proof": proof_dict}
        )
        if claimed < 1 or claimed > len(self.public_shares):
            return RejectedResponse(claimed, "operator id out of range")
        if not verify_partial(self.public_shares[claimed - 1], ciphertext, partial, epoch):
            return RejectedResponse(claimed, "Chaum-Pedersen proof does not verify")

        # 7. the answer came from the operator that was asked
        if claimed != operator_id:
            return RejectedResponse(claimed, f"operator {operator_id} was asked, {claimed} answered")

        self.seen_nonces.add(nonce)
        response_hash = sha256_hex(canonical_json_bytes(payload))
        return VerifiedResponse(
            operator_id=claimed,
            host_id=str(payload["host_id"]),
            partial=partial,
            partial_hash=partial_hash,
            proof_hash=proof_hash,
            response_hash=response_hash,
            nonce=nonce,
            runtime_source_digest=self.expected_runtime_source_digest,
        )

    # --- request ---------------------------------------------------------
    def request(
        self,
        operator_id: int,
        *,
        order_id: str,
        buyer: str,
        resource: str,
        epoch: int,
        ciphertext: Ciphertext,
        nonce: str,
        ttl_s: float = 30.0,
        tamper: str | None = None,
        replay_payload: Mapping[str, object] | None = None,
    ) -> tuple[VerifiedResponse | RejectedResponse, Mapping[str, object] | None, float]:
        endpoint = self.endpoints.get(operator_id)
        if endpoint is None:
            return RejectedResponse(operator_id, "no endpoint configured"), None, 0.0
        started = time.perf_counter()
        if replay_payload is not None:
            payload: Mapping[str, object] | None = replay_payload
        else:
            # The coordinator supplies no proof randomness. The operator derives
            # its Chaum--Pedersen nonce internally from its own share, so host 1
            # cannot steer it into reusing a witness across two ciphertexts.
            body = {
                "protocol_version": PROTOCOL_VERSION,
                "order_id": order_id,
                "buyer": buyer,
                "resource": resource,
                "epoch": epoch,
                "ciphertext": ciphertext.to_dict(),
                "nonce": nonce,
                "expires_at": time.time() + ttl_s,
            }
            try:
                payload = self._post(endpoint, body)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
                elapsed = (time.perf_counter() - started) * 1000
                reason = f"transport failure: {type(error).__name__}"
                self.transcript.append(
                    {"event": "request_failed", "operator_id": operator_id, "order_id": order_id, "reason": reason}
                )
                return RejectedResponse(operator_id, reason), None, elapsed
        outcome = self._verify(
            payload,
            operator_id=operator_id,
            order_id=order_id,
            buyer=buyer,
            resource=resource,
            epoch=epoch,
            nonce=nonce,
            ciphertext=ciphertext,
            tamper=tamper,
        )
        elapsed = (time.perf_counter() - started) * 1000
        self.transcript.append(
            {
                "event": "verified" if isinstance(outcome, VerifiedResponse) else "rejected",
                "operator_id": operator_id,
                "order_id": order_id,
                "detail": outcome.to_dict(),
            }
        )
        return outcome, payload, elapsed

