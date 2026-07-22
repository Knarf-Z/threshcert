#!/usr/bin/env python3
"""Report the recorded Chiado slashing transaction's fee versus the bond it recovered.

Purely additive: reads the already-recorded `results/slashing-chiado.json`
(the same file `verify_chiado_certificate.py` binds into the certificate)
without modifying it or that certificate, whose `certificateId` is a hash of
its own payload and is cited by exact value elsewhere (RESULTS_SUMMARY.md,
CHANGELOG.md). This script only computes and prints one additional derived
number: the ratio of the slashing transaction's own gas cost to the bond
amount it forfeited, backing the paper's incentive-defect observation with a
reproducible check rather than a hand-computed figure in prose.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLASHING_PATH = ROOT / "results" / "slashing-chiado.json"


def main() -> None:
    with SLASHING_PATH.open(encoding="utf-8") as handle:
        slashing = json.load(handle)

    transaction = slashing["transaction"]
    gas_used = int(transaction["gasUsed"])
    effective_gas_price_wei = int(transaction["effectiveGasPrice"])
    fee_wei = gas_used * effective_gas_price_wei

    bond_forfeited_wei = int(slashing["certificateBeforeWei"]) - int(
        slashing["certificateAfterWei"]
    )
    if bond_forfeited_wei <= 0:
        raise SystemExit("recorded slashing did not reduce the certificate")

    ratio = fee_wei / bond_forfeited_wei

    print(f"gas_used={gas_used}")
    print(f"effective_gas_price_wei={effective_gas_price_wei}")
    print(f"fee_wei={fee_wei}")
    print(f"bond_forfeited_wei={bond_forfeited_wei}")
    print(f"fee_to_bond_ratio={ratio:.6f}")
    print(
        "incentive_status="
        + ("FEE_EXCEEDS_BOND" if fee_wei > bond_forfeited_wei else "BOND_COVERS_FEE")
    )


if __name__ == "__main__":
    main()
