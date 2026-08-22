"""The one-time key ceremony, and the boundary it draws.

This module is the *only* place the full secret material exists together. It runs
once, on the dealer, during setup. It writes two kinds of file:

* one public committee bundle, shipped to both hosts, that contains public keys,
  public shares and network public keys and *no* seed and *no* secret;
* one secret file per operator, each containing exactly one operator's threshold
  share and network secret key.

After setup, each host holds the public bundle and only its own operators' secret
files. Host 1 cannot reconstruct operators 2, 4, 6, 7: the material to do so is
not on its disk, and the public bundle does not contain the seed that would let
it regenerate them.

This is a *trusted-dealer* model, and the paper says so. At ceremony time the
dealer necessarily computes every share; that single trusted step is a declared
assumption, distinct from the run-time claim the experiment actually tests, which
is that at experiment time neither host's files suffice to reconstruct the other's
shares. A deployment would replace this ceremony with a distributed key
generation; nothing here claims to.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from .crypto import ThresholdKeySet
from .network_identity import NetworkIdentity
from .utils import write_json

PUBLIC_SCHEMA = "ptr-two-host-committee-public/v3"
SECRET_SCHEMA = "ptr-two-host-operator-secret/v3"

# Fields whose presence in a distributed artifact would defeat the whole point.
FORBIDDEN_PUBLIC_FIELDS = ("seed", "network_seed", "secret_shares", "network_secret_key", "secret_share")


@dataclass(frozen=True)
class DealtCommittee:
    public_bundle: dict[str, object]
    secrets_by_operator: dict[int, dict[str, object]]


def deal(meta: Mapping[str, object], seed: int, network_seed: int) -> DealtCommittee:
    """Run the ceremony from public metadata plus the two dealer seeds.

    ``meta`` is the non-secret committee description (sizes, floors, buyer,
    resource, epoch, host assignment). ``seed`` and ``network_seed`` are the
    dealer's one-time randomness; they are consumed here and must never be
    written into any shipped file.
    """

    size = int(meta["committee_size"])
    threshold = int(meta["threshold"])
    operator_hosts = {int(k): str(v) for k, v in dict(meta["operator_hosts"]).items()}

    keyset = ThresholdKeySet.generate(size, threshold, seed=seed)
    identities = {
        operator_id: NetworkIdentity.derive(operator_id, operator_hosts[operator_id], network_seed)
        for operator_id in range(1, size + 1)
    }

    public_bundle: dict[str, object] = {
        "schema": PUBLIC_SCHEMA,
        "committee_size": size,
        "threshold": threshold,
        "response_floors": [int(v) for v in meta["response_floors"]],
        "buyer": str(meta["buyer"]),
        "resource": str(meta["resource"]),
        "epoch": int(meta["epoch"]),
        "operator_hosts": {str(k): v for k, v in sorted(operator_hosts.items())},
        "public_key": hex(keyset.public_key),
        "public_shares": {str(i): hex(keyset.public_shares[i - 1]) for i in range(1, size + 1)},
        "network_public_keys": {str(i): hex(identities[i].public_key) for i in range(1, size + 1)},
    }
    _assert_public_clean(public_bundle)

    secrets_by_operator = {
        operator_id: {
            "schema": SECRET_SCHEMA,
            "operator_id": operator_id,
            "host_id": operator_hosts[operator_id],
            "secret_share": hex(keyset.secret_shares[operator_id - 1]),
            "public_share": hex(keyset.public_shares[operator_id - 1]),
            "network_secret_key": hex(identities[operator_id].secret_key),
            "network_public_key": hex(identities[operator_id].public_key),
        }
        for operator_id in range(1, size + 1)
    }
    return DealtCommittee(public_bundle, secrets_by_operator)


def _assert_public_clean(bundle: Mapping[str, object]) -> None:
    rendered = json.dumps(bundle)
    for field in FORBIDDEN_PUBLIC_FIELDS:
        if field in bundle:
            raise AssertionError(f"public bundle must not contain field {field!r}")
    # A defensive scan of the serialized text, in case a nested structure sneaks
    # a secret in under a different key.
    for needle in ("secret", "\"seed\""):
        if needle in rendered:
            raise AssertionError(f"public bundle serialization contains {needle!r}")


def write_dealt(
    dealt: DealtCommittee,
    *,
    public_path: Path,
    secret_dir: Path,
    operators: list[int] | None = None,
) -> list[Path]:
    """Write the public bundle and a chosen subset of operator secret files.

    ``operators`` selects which operators' secret files land in ``secret_dir``;
    the setup script calls this once per host with that host's operators, so a
    host's disk never receives another host's secret.
    """

    write_json(public_path, dealt.public_bundle)
    written = [public_path]
    chosen = operators if operators is not None else sorted(dealt.secrets_by_operator)
    secret_dir.mkdir(parents=True, exist_ok=True)
    for operator_id in chosen:
        path = secret_dir / f"operator-{operator_id}.secret.json"
        write_json(path, dealt.secrets_by_operator[operator_id])
        written.append(path)
    return written

