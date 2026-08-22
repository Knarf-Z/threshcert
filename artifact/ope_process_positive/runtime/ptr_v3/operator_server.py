"""One operator, exposed over HTTP.

The interface is deliberately two endpoints. There is no ``/export``,
``/share``, ``/debug/share`` or ``/admin/dump``: the (C1) witness records the
served route table, so anything reachable here would have to be disclosed there.

The server never sees the buyer's ledger and never decides whether a response is
counted; it computes a partial decryption, proves it against its public share,
and signs the whole context with its network key.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time

if __package__ in (None, ""):  # allow `python src/ptr_v3/operator_server.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ptr_v3.crypto import Ciphertext, create_partial
from ptr_v3.network_identity import NetworkIdentity, PROTOCOL_VERSION, sign, signing_message
from ptr_v3.utils import canonical_json_bytes, file_sha256, sha256_hex

SERVED_ROUTES = ("POST /respond", "GET /health")
RUNTIME_SOURCE_FILES = ("__init__.py", "crypto.py", "network_identity.py", "operator_server.py", "utils.py")


def runtime_source_digest() -> str:
    base = Path(__file__).resolve().parent
    hashes = {name: file_sha256(base / name) for name in RUNTIME_SOURCE_FILES}
    return sha256_hex(canonical_json_bytes(hashes))


RUNTIME_SOURCE_DIGEST = runtime_source_digest()


def machine_digest() -> str:
    """A self-reported fingerprint of the machine this operator runs on.

    Two operators on the same machine necessarily report the same digest, so a
    collision refutes a two-host claim. A difference does not prove separation:
    the value is self-reported and unattested, exactly like every other host
    claim in this experiment. Host 1 pairs it with the observed TCP peer address
    before concluding anything.
    """

    return sha256_hex(
        canonical_json_bytes(
            {
                "node": platform.node(),
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "cpu_count": os.cpu_count(),
            }
        )
    )[:32]


MACHINE_DIGEST = machine_digest()


class OperatorState:
    def __init__(
        self,
        operator_id: int,
        host_id: str,
        share: int,
        public_share: int,
        identity: NetworkIdentity,
        transcript_path: Path | None = None,
        nonce_path: Path | None = None,
    ):
        self.operator_id = operator_id
        self.host_id = host_id
        self.share = share
        self.public_share = public_share
        self.identity = identity
        self.lock = threading.Lock()
        self.transcript_path = transcript_path
        self.nonce_path = nonce_path
        self.transcript: list[dict[str, object]] = []
        self.artificial_delay_ms = 0.0
        # Replay protection survives a restart: nonces are loaded from disk and
        # every accepted nonce is appended and flushed before the response goes
        # out, so a killed process cannot forget what it already answered.
        self.seen_nonces: set[str] = self._load_nonces()

    def _load_nonces(self) -> set[str]:
        if self.nonce_path and self.nonce_path.exists():
            with self.nonce_path.open("r", encoding="utf-8") as handle:
                return {line.strip() for line in handle if line.strip()}
        return set()

    def _append_line(self, path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def remember_nonce(self, nonce: str) -> None:
        """Persist an accepted nonce. Caller holds ``self.lock``."""
        self.seen_nonces.add(nonce)
        if self.nonce_path:
            self._append_line(self.nonce_path, nonce)

    def record(self, entry: dict[str, object]) -> None:
        with self.lock:
            self.transcript.append(entry)
            if self.transcript_path:
                self._append_line(self.transcript_path, json.dumps(entry, sort_keys=True))


def _partial_and_proof(state: OperatorState, ciphertext: Ciphertext, epoch: int):
    response = create_partial(state.operator_id, state.share, state.public_share, ciphertext, epoch)
    partial_hash = sha256_hex(canonical_json_bytes({"value": hex(response.value)}))
    proof_hash = sha256_hex(canonical_json_bytes(response.proof.to_dict()))
    return response, partial_hash, proof_hash


def build_handler(state: OperatorState):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "ptr-v3-operator"
        sys_version = ""

        def log_message(self, *args) -> None:  # keep stdout clean for the harness
            return

        def _send(self, code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self._send(404, {"error": "no such route", "served": list(SERVED_ROUTES)})
                return
            self._send(
                200,
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "operator_id": state.operator_id,
                    "host_id": state.host_id,
                    "network_public_key": hex(state.identity.public_key),
                    "public_share": hex(state.public_share),
                    "served_routes": list(SERVED_ROUTES),
                    "machine_digest": MACHINE_DIGEST,
                    "runtime_source_digest": RUNTIME_SOURCE_DIGEST,
                },
            )

        def do_POST(self) -> None:
            if self.path != "/respond":
                self._send(404, {"error": "no such route", "served": list(SERVED_ROUTES)})
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                request = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send(400, {"error": "malformed request"})
                return

            if state.artificial_delay_ms:
                time.sleep(state.artificial_delay_ms / 1000.0)

            required = (
                "protocol_version",
                "order_id",
                "buyer",
                "resource",
                "epoch",
                "ciphertext",
                "nonce",
                "expires_at",
            )
            missing = [field for field in required if field not in request]
            if missing:
                self._send(400, {"error": "missing fields", "fields": missing})
                return
            if request["protocol_version"] != PROTOCOL_VERSION:
                self._send(400, {"error": "protocol version mismatch"})
                return
            if float(request["expires_at"]) < time.time():
                self._send(409, {"error": "request expired"})
                return

            nonce = str(request["nonce"])
            with state.lock:
                replayed = nonce in state.seen_nonces
                if not replayed:
                    state.remember_nonce(nonce)
            if replayed:
                state.record({"event": "nonce_rejected", "order_id": request["order_id"], "nonce": nonce})
                self._send(409, {"error": "nonce already used"})
                return

            ciphertext = Ciphertext.from_dict(request["ciphertext"])
            if ciphertext.buyer != request["buyer"] or ciphertext.resource != request["resource"]:
                self._send(400, {"error": "ciphertext context does not match the request"})
                return

            response, partial_hash, proof_hash = _partial_and_proof(state, ciphertext, int(request["epoch"]))
            message = signing_message(
                operator_id=state.operator_id,
                host_id=state.host_id,
                order_id=str(request["order_id"]),
                buyer=str(request["buyer"]),
                resource=str(request["resource"]),
                epoch=int(request["epoch"]),
                partial_hash=partial_hash,
                proof_hash=proof_hash,
                nonce=nonce,
                runtime_source_digest=RUNTIME_SOURCE_DIGEST,
            )
            signature = sign(state.identity, message)
            payload = {
                "protocol_version": PROTOCOL_VERSION,
                "operator_id": state.operator_id,
                "host_id": state.host_id,
                "order_id": request["order_id"],
                "buyer": request["buyer"],
                "resource": request["resource"],
                "epoch": int(request["epoch"]),
                "nonce": nonce,
                "partial_decryption": hex(response.value),
                "chaum_pedersen_proof": response.proof.to_dict(),
                "partial_hash": partial_hash,
                "proof_hash": proof_hash,
                "operator_signature": signature.to_dict(),
                "runtime_source_digest": RUNTIME_SOURCE_DIGEST,
            }
            state.record(
                {
                    "event": "responded",
                    "order_id": request["order_id"],
                    "operator_id": state.operator_id,
                    "host_id": state.host_id,
                    "nonce": nonce,
                    "partial_hash": partial_hash,
                    "proof_hash": proof_hash,
                }
            )
            self._send(200, payload)

    return Handler


def serve(state: OperatorState, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), build_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one PTR v3 operator.")
    parser.add_argument("--operator-id", type=int, required=True)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--secret", type=Path, required=True, help="this operator's secret file")
    parser.add_argument("--public", type=Path, required=True, help="the public committee bundle")
    parser.add_argument("--transcript", type=Path, default=None, help="append-only transcript path")
    parser.add_argument("--nonce-log", type=Path, default=None, help="persistent replay-protection log")
    args = parser.parse_args()

    secret = json.loads(args.secret.read_text(encoding="utf-8"))
    public = json.loads(args.public.read_text(encoding="utf-8"))
    if int(secret["operator_id"]) != args.operator_id:
        print(f"SECRET_OPERATOR_MISMATCH secret={secret['operator_id']} arg={args.operator_id}")
        return 1
    for field in ("seed", "network_seed", "secret_shares"):
        if field in public:
            print(f"PUBLIC_BUNDLE_CARRIES_SECRET={field}")
            return 1

    operator_id = args.operator_id
    host_id = str(secret["host_id"])
    # The public share is cross-checked against the public bundle, so a secret
    # file cannot silently claim a different identity than the committee agreed.
    public_share = int(str(public["public_shares"][str(operator_id)]), 16)
    if int(str(secret["public_share"]), 16) != public_share:
        print("PUBLIC_SHARE_MISMATCH")
        return 1
    identity = NetworkIdentity.from_secret(operator_id, host_id, int(str(secret["network_secret_key"]), 16))
    if identity.public_key != int(str(public["network_public_keys"][str(operator_id)]), 16):
        print("NETWORK_PUBLIC_KEY_MISMATCH")
        return 1

    state = OperatorState(
        operator_id=operator_id,
        host_id=host_id,
        share=int(str(secret["secret_share"]), 16),
        public_share=public_share,
        identity=identity,
        transcript_path=args.transcript,
        nonce_path=args.nonce_log,
    )
    server = serve(state, args.bind, args.port)
    print(f"OPERATOR_READY id={operator_id} host={host_id} port={args.port}")
    print(f"OPERATOR_NETWORK_PUBLIC_KEY={hex(identity.public_key)}")
    sys.stdout.flush()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

