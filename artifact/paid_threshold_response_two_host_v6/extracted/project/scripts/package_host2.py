"""Build the host-2 half of the deployment as a single zip.

Host 2 runs four operators and nothing else. The bundle carries:

* the operator source (no dealer, no coordinator);
* the *public* committee bundle -- public keys only, no seed, no secret;
* host 2's four operator secret files, and no others;
* host 2's port map and the three PowerShell scripts it needs.

It deliberately does not carry the dealer seed, the committee metadata seeds, or
any host-1 secret. A host 2 that unpacks this bundle cannot reconstruct host 1's
shares, and host 1 never shipped host 2's shares to anyone else.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.dealer import deal, write_dealt  # noqa: E402
from ptr_v3.utils import canonical_json_bytes, read_json  # noqa: E402

SOURCE_MODULES = (
    "__init__.py",
    "crypto.py",
    "network_identity.py",
    "operator_server.py",
    "utils.py",
)

README = """# Host 2 -- operator half of the V5 controlled two-host artifact

This machine runs four of the seven committee operators (2, 4, 6, 7). It holds
its own four secret shares and no others. It never holds the threshold key as a
whole, never aggregates, and never learns a plaintext. It answers `POST /respond`
with a partial decryption plus a Chaum-Pedersen proof, signed under its Schnorr network key. Every signed response also binds a
runtime digest of the five operator modules; Host 1 rejects a digest mismatch.

The proof nonce is derived inside the operator from its own share and the
ciphertext; the requester has no input to it. This is what stops host 1 from
extracting a share with two crafted queries.

Requires Python 3.10 or newer on PATH as `py -3`. No third-party packages.

## 1. Unpack and check

    Expand-Archive host2_bundle.zip -DestinationPath C:\\ptr_host2
    cd C:\\ptr_host2
    py -3 -c "import sys; print(sys.version)"

## 2. Open the firewall to host 1 only (run as Administrator)

Replace the placeholder with host 1's LAN address.

    .\\powershell\\Open-Host2-Firewall.ps1 -Host1Address HOST1_LAN_ADDRESS

## 3. Start the operators

    .\\powershell\\Start-Operators.ps1 -HostId host2

Expect `HOST2_OPERATORS_READY=4`. The operators load their secret shares from
`secrets\\host2\\` and the public keys from `config\\committee.public.v3.json`.
The script refuses to start if this machine holds a secret file for an operator
it does not run.

## 4. Tell host 1 this machine's LAN address

    Get-NetIPAddress -AddressFamily IPv4 |
      Where-Object { $_.PrefixOrigin -ne "WellKnown" } |
      Select-Object -ExpandProperty IPAddress

Send that address to host 1. Host 1 writes it into `config/topology.v3.json` and
runs the experiment.

## During the experiment

Host 1 will ask you to do two things at specific points:

* **Outage test (groups C and D).** Run `.\\powershell\\Stop-Operators.ps1
  -HostId host2` and tell host 1. Host 1 then shows that a 4-of-7 threshold
  cannot be reached, that no partial plaintext is released, and that no local
  operator is silently substituted for a remote one.
* **Recovery test.** Run `.\\powershell\\Start-Operators.ps1 -HostId host2`
  again and tell host 1.

Replay protection persists to `results\\host2\\operator-*.nonces.log`, so a
restart does not forget answered orders. Host 1's runner salts each run with a
fresh id, so a legitimate re-run is never rejected as a replay.

## What is in this bundle

    src/ptr_v3/operator_server.py       the four-operator HTTP service
    src/ptr_v3/network_identity.py      Schnorr identity from a loaded secret key
    src/ptr_v3/crypto.py                threshold ElGamal, Chaum-Pedersen proofs
    src/ptr_v3/utils.py                 canonical JSON and hashing
    config/committee.public.v3.json     public keys and shares -- NO seed, NO secret
    config/host2.v3.json                this host's operators and ports
    secrets/host2/operator-2,4,6,7.secret.json   this host's four shares
    powershell/                         start, stop, firewall

There is no `seed`, no `network_seed`, and no other host's secret anywhere in
this bundle. Host 1's shares are not derivable from anything here.
"""


def _members(public_bundle_bytes: bytes, host2_secrets: dict[int, bytes]) -> list[tuple[str, bytes]]:
    members: list[tuple[str, bytes]] = []
    for name in SOURCE_MODULES:
        members.append((f"src/ptr_v3/{name}", (ROOT / "src" / "ptr_v3" / name).read_bytes()))
    members.append(("config/committee.public.v3.json", public_bundle_bytes))
    members.append(("config/host2.v3.json", (ROOT / "config" / "host2.v3.json").read_bytes()))
    for operator_id, blob in sorted(host2_secrets.items()):
        members.append((f"secrets/host2/operator-{operator_id}.secret.json", blob))
    for name in ("Start-Operators.ps1", "Stop-Operators.ps1", "Open-Host2-Firewall.ps1"):
        members.append((f"powershell/{name}", (ROOT / "powershell" / name).read_bytes()))
    members.append(("README.md", README.encode("utf-8")))
    return members


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the host-2 half.")
    parser.add_argument("--meta", type=Path, default=ROOT / "config" / "committee.meta.v3.json")
    parser.add_argument("--dealer-seed", type=Path, default=ROOT / "config" / "dealer_seed.v3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "host2_bundle.zip")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    meta = read_json(args.meta)
    seeds = read_json(args.dealer_seed)
    operator_hosts = {int(k): str(v) for k, v in meta["operator_hosts"].items()}
    host2_ops = sorted(op for op, host in operator_hosts.items() if host == "host2")

    dealt = deal(meta, seed=int(seeds["seed"]), network_seed=int(seeds["network_seed"]))

    # Ship the exact bytes host 1 runs from, so the two hosts cannot disagree on
    # the committee. If host 1 has not been set up yet, mint the file now with the
    # same writer, then ship those bytes.
    runtime_public = ROOT / "config" / "committee.public.v3.json"
    if not runtime_public.exists():
        write_dealt(dealt, public_path=runtime_public, secret_dir=args.output.parent / "_unused", operators=[])
    public_bytes = runtime_public.read_bytes()
    if json.loads(public_bytes) != dealt.public_bundle:
        print("PUBLIC_BUNDLE_DRIFT: config/committee.public.v3.json content differs from the dealt bundle")
        return 1

    # Secret files are shipped as the same writer produces them on disk.
    from ptr_v3.utils import write_json

    staging = args.output.parent / "_host2_secret_staging"
    write_dealt(dealt, public_path=staging / "public.json", secret_dir=staging, operators=host2_ops)
    host2_secrets = {op: (staging / f"operator-{op}.secret.json").read_bytes() for op in host2_ops}

    members = _members(public_bytes, host2_secrets)
    manifest_lines = [
        f"{sha256(blob).hexdigest().upper()}  {arcname}"
        for arcname, blob in sorted(members, key=lambda pair: pair[0])
    ]
    members.append(("HOST2_MANIFEST.sha256", ("\n".join(manifest_lines) + "\n").encode("ascii")))
    # Guard: nothing secret for another host, nothing seed-like.
    for arcname, blob in members:
        if arcname.startswith("secrets/") and not arcname.startswith("secrets/host2/"):
            print(f"REFUSING_FOREIGN_SECRET={arcname}")
            return 1
        if arcname.endswith(".json") and arcname.startswith("config/"):
            parsed = json.loads(blob)
            if any(k in parsed for k in ("seed", "network_seed", "secret_shares")):
                print(f"REFUSING_SEED_IN_CONFIG={arcname}")
                return 1

    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for arcname, blob in sorted(members, key=lambda pair: pair[0]):
            info = zipfile.ZipInfo(arcname, date_time=(2026, 8, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, blob)

    digest = sha256(args.output.read_bytes()).hexdigest()
    print(f"HOST2_BUNDLE={args.output}")
    print(f"HOST2_SECRET_OPERATORS={','.join(map(str, host2_ops))}")
    print(f"HOST2_BUNDLE_FILES={len(members)}")
    print(f"HOST2_BUNDLE_SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
