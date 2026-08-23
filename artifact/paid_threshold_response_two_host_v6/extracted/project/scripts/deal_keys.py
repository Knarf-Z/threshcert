"""Run the key ceremony and write per-host material.

On host 1 (the dealer):

    py -3 scripts/deal_keys.py --host host1

writes the public committee bundle plus secret files for operators 1, 3, 5 into
``secrets/host1/``. To stage the host-2 material for the bundle:

    py -3 scripts/deal_keys.py --host host2 --secret-dir dist/host2_staging/secrets

The seeds are read from ``config/dealer_seed.v3.json`` and never leave this
machine. The command refuses to write a secret file for an operator that is not
assigned to the requested host.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.dealer import deal, write_dealt  # noqa: E402
from ptr_v3.utils import read_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Deal committee keys for one host.")
    parser.add_argument("--host", required=True, help="which host's secrets to write (host1 / host2)")
    parser.add_argument("--meta", type=Path, default=ROOT / "config" / "committee.meta.v3.json")
    parser.add_argument("--dealer-seed", type=Path, default=ROOT / "config" / "dealer_seed.v3.json")
    parser.add_argument("--public", type=Path, default=ROOT / "config" / "committee.public.v3.json")
    parser.add_argument("--secret-dir", type=Path, default=None)
    args = parser.parse_args()

    meta = read_json(args.meta)
    seeds = read_json(args.dealer_seed)
    operator_hosts = {int(k): str(v) for k, v in meta["operator_hosts"].items()}
    this_host = [i for i, h in sorted(operator_hosts.items()) if h == args.host]
    if not this_host:
        print(f"NO_OPERATORS_FOR_HOST={args.host}")
        return 1

    secret_dir = args.secret_dir or (ROOT / "secrets" / args.host)
    dealt = deal(meta, seed=int(seeds["seed"]), network_seed=int(seeds["network_seed"]))
    written = write_dealt(dealt, public_path=args.public, secret_dir=secret_dir, operators=this_host)

    print(f"PUBLIC_BUNDLE={args.public}")
    print(f"HOST={args.host}")
    print(f"SECRET_OPERATORS={','.join(map(str, this_host))}")
    print(f"SECRET_DIR={secret_dir}")
    print(f"FILES_WRITTEN={len(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
