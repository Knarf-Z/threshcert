"""Groups C and D: what happens when host 2 is unreachable.

The point is not that the certificate drops to zero. It is that no usable
threshold output is produced at all, and that the coordinator does not silently
substitute a locally available operator for the unreachable one.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import secrets
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptr_v3.evidence import CERTIFIED  # noqa: E402
from ptr_v3.experiment import Committee, assess, run_order  # noqa: E402
from ptr_v3.utils import file_sha256, read_json, write_json  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from run_two_host import build_coordinator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Host 2 outage tests (groups C and D).")
    parser.add_argument("--committee", type=Path, default=ROOT / "config" / "committee.public.v3.json")
    parser.add_argument("--topology", type=Path, default=ROOT / "config" / "topology.v3.json")
    parser.add_argument("--host1", type=Path, default=ROOT / "config" / "host1.v3.json")
    parser.add_argument("--host2", type=Path, default=ROOT / "config" / "host2.v3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "outage_result.v3.json")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--recovery", action="store_true", help="also run a fresh order after recovery")
    args = parser.parse_args()

    manifest_digest_path = ROOT / "config" / "code_manifest.v1.sha256"
    canonical_path = ROOT / "results" / "canonical_result.v3.json"
    if not manifest_digest_path.exists() or not canonical_path.exists():
        raise RuntimeError("final code manifest and canonical result are required")
    code_manifest_sha256 = manifest_digest_path.read_text(encoding="ascii").strip().upper()
    canonical_result_sha256 = file_sha256(canonical_path).upper()

    committee = Committee.from_file(args.committee)
    topology = read_json(args.topology)
    h1, h2 = read_json(args.host1), read_json(args.host2)
    ports = {int(k): int(v) for k, v in {**h1["ports"], **h2["ports"]}.items()}
    registry, coordinator = build_coordinator(committee, topology, ports, args.timeout)
    floors = list(committee.response_floors)

    reachable = {i: coordinator.health(i) is not None for i in sorted(committee.operator_hosts)}
    host2_ops = committee.operators_on("host2")
    host2_down = not any(reachable[i] for i in host2_ops)

    cheapest = [i + 1 for i, _ in sorted(enumerate(floors), key=lambda kv: kv[1])[: committee.threshold]]
    suffix = "recovery" if args.recovery else "outage"
    # A fresh run id keeps persistent replay logs from rejecting a re-run.
    run_id = secrets.token_hex(4)

    # C: the minimum-cover coalition spans both hosts
    out_c, _ = run_order(
        coordinator, committee, order_id=f"{run_id}-C-{suffix}", coalition=cheapest
    )
    _, _, _, rep_c = assess(out_c, committee)

    # D: a coalition host 1 could almost serve alone, still short one remote member
    host1_ops = committee.operators_on("host1")
    alternative = sorted(host1_ops + [min(host2_ops)])[: committee.threshold]
    if len(alternative) < committee.threshold:
        alternative = sorted(set(host1_ops + host2_ops))[: committee.threshold]
    out_d, _ = run_order(
        coordinator, committee, order_id=f"{run_id}-D-{suffix}", coalition=alternative
    )
    _, _, _, rep_d = assess(out_d, committee)

    result: dict[str, Any] = {
        "schema": "paid-threshold-response-two-host-outage/v5",
        "source_binding": {
            "code_manifest_sha256": code_manifest_sha256,
            "canonical_result_sha256": canonical_result_sha256,
        },
        "host2_unreachable": host2_down,
        "reachable": {str(k): v for k, v in sorted(reachable.items())},
        "C_minimum_cover_coalition": {
            "coalition": cheapest,
            "responses_received": len(out_c.verified),
            "threshold_reached": out_c.threshold_reached,
            "gateway_accepted": out_c.gateway_accepted,
            "usable_plaintext_released": out_c.plaintext is not None,
            "rejections": [r.to_dict() for r in out_c.rejected],
            "status": rep_c.status,
            "execution_floor": rep_c.execution_floor,
        },
        "D_alternative_coalition": {
            "coalition": alternative,
            "responses_received": len(out_d.verified),
            "threshold_reached": out_d.threshold_reached,
            "gateway_accepted": out_d.gateway_accepted,
            "usable_plaintext_released": out_d.plaintext is not None,
            "status": rep_d.status,
        },
    }

    if args.recovery:
        checks = {
            "host2_reachable_again": not host2_down,
            "new_order_succeeds": rep_c.status == CERTIFIED and out_c.plaintext is not None,
            "floor_recovered": rep_c.execution_floor == sum(floors[i - 1] for i in cheapest),
        }
    else:
        checks = {
            "host2_confirmed_unreachable": host2_down,
            "threshold_not_reached": not out_c.threshold_reached,
            "gateway_refused": not out_c.gateway_accepted,
            "no_usable_plaintext_release": out_c.plaintext is None,
            "no_local_substitution": all(
                r.operator_id in cheapest for r in out_c.verified
            )
            and len(out_c.verified) == len([i for i in cheapest if reachable[i]]),
            "alternative_coalition_also_fails": not out_d.gateway_accepted and out_d.plaintext is None,
        }
    result["checks"] = checks
    write_json(args.output, result)

    print(f"HOST2_UNREACHABLE={str(host2_down).lower()}")
    print(f"RESPONSES_RECEIVED={len(out_c.verified)}")
    print(f"THRESHOLD_REACHED={str(out_c.threshold_reached).lower()}")
    print(f"GATEWAY_ACCEPTED={str(out_c.gateway_accepted).lower()}")
    if args.recovery:
        print(f"USABLE_PLAINTEXT_RELEASED={str(out_c.plaintext is not None).lower()}")
    else:
        print(f"NO_PARTIAL_PLAINTEXT_RELEASE={'PASS' if out_c.plaintext is None else 'FAIL'}")
    print(f"ALTERNATIVE_COALITION_{''.join(map(str, alternative))}_ACCEPTED={str(out_d.gateway_accepted).lower()}")
    failed = [k for k, v in checks.items() if not v]
    if failed:
        print("FAILED_CHECKS=" + ",".join(sorted(failed)))
        return 1
    print("REMOTE_THRESHOLD_DEPENDENCY=CONFIRMED" if not args.recovery else "NETWORK_RECOVERY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
