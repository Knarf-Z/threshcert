from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from common import RESULTS, ensure_results, write_csv, write_json


SELECTORS = {
    "getNumKeyperSets": "0xf2e6100a",
    "getKeyperSetIndexByBlock": "0x035cef15",
    "getKeyperSetAddress": "0xf90f3bed",
    "getKeyperSetActivationBlock": "0x636df979",
    "getMembers": "0x9eab5253",
    "getNumMembers": "0x17d5430a",
    "getThreshold": "0xe75235b8",
    "getPublisher": "0xdbf4ab4e",
    "isFinalized": "0x8d4e4083",
    "owner": "0x8da5cb5b",
}

MISSING_PERIOD_EVIDENCE = "NOT_EVALUATED_MISSING_PERIOD_EVIDENCE"
ZERO_PUBLIC_FLOOR_CERTIFICATE = "0_PUBLIC_FLOOR_CERTIFICATE"


class RpcClient:
    def __init__(
        self,
        url: str,
        max_attempts: int = 4,
        timeout_seconds: int = 45,
        retry_base_seconds: int = 2,
    ) -> None:
        self.url = url
        self.identifier = 0
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds
        self.retry_base_seconds = retry_base_seconds

    def _post(self, payload_object: Any) -> Any:
        payload = json.dumps(payload_object).encode("utf-8")
        for attempt in range(1, self.max_attempts + 1):
            request = Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (URLError, TimeoutError, OSError) as error:
                if attempt == self.max_attempts:
                    raise RuntimeError(
                        "RPC transport failed after "
                        f"{self.max_attempts} attempts: {error}"
                    ) from error
                delay = self.retry_base_seconds * (2 ** (attempt - 1))
                print(
                    f"RPC transport retry {attempt}/{self.max_attempts - 1} "
                    f"after {delay}s: {error}",
                    flush=True,
                )
                time.sleep(delay)
        raise AssertionError("unreachable RPC retry state")

    def call(self, method: str, params: list[Any]) -> Any:
        self.identifier += 1
        body = self._post({
            "jsonrpc": "2.0",
            "id": self.identifier,
            "method": method,
            "params": params,
        })
        if "error" in body:
            raise RuntimeError(f"RPC {method} failed: {body['error']}")
        return body["result"]

    def eth_call(self, address: str, data: str, block_tag: str) -> str:
        return self.call("eth_call", [{"to": address, "data": data}, block_tag])

    def batch_eth_call(
        self,
        calls: list[tuple[str, str]],
        block_tag: str,
    ) -> list[str]:
        requests = []
        request_ids = []
        for address, data in calls:
            self.identifier += 1
            request_ids.append(self.identifier)
            requests.append({
                "jsonrpc": "2.0",
                "id": self.identifier,
                "method": "eth_call",
                "params": [{"to": address, "data": data}, block_tag],
            })
        bodies = self._post(requests)
        if not isinstance(bodies, list):
            raise RuntimeError("batch eth_call returned a non-list response")
        by_id = {body["id"]: body for body in bodies}
        results = []
        for request_id in request_ids:
            body = by_id.get(request_id)
            if body is None:
                raise RuntimeError(
                    f"batch eth_call omitted response id {request_id}"
                )
            if "error" in body:
                raise RuntimeError(
                    f"batch eth_call id {request_id} failed: {body['error']}"
                )
            results.append(body["result"])
        return results


def encode_uint(value: int) -> str:
    return f"{value:064x}"


def decode_uint(data: str) -> int:
    return int(data[2:66], 16)


def decode_address(data: str) -> str:
    return "0x" + data[2:66][-40:]


def decode_bool(data: str) -> bool:
    return bool(decode_uint(data))


def decode_address_array(data: str) -> list[str]:
    raw = bytes.fromhex(data[2:])
    offset = int.from_bytes(raw[:32], "big")
    length = int.from_bytes(raw[offset : offset + 32], "big")
    return [
        "0x" + raw[offset + 32 + i * 32 : offset + 64 + i * 32][-20:].hex()
        for i in range(length)
    ]


def decode_keyper_set_added(data: str) -> dict[str, Any]:
    """Decode KeyperSetAdded(uint64,address,address[],uint64,uint64)."""
    raw = bytes.fromhex(data[2:])
    if len(raw) < 160:
        raise ValueError("KeyperSetAdded data is shorter than five ABI words")

    def word(index: int) -> bytes:
        return raw[index * 32 : (index + 1) * 32]

    members_offset = int.from_bytes(word(2), "big")
    if members_offset + 32 > len(raw):
        raise ValueError("KeyperSetAdded members offset is out of bounds")
    members_length = int.from_bytes(
        raw[members_offset : members_offset + 32], "big"
    )
    members_end = members_offset + 32 + members_length * 32
    if members_end > len(raw):
        raise ValueError("KeyperSetAdded members array is truncated")
    members = [
        "0x"
        + raw[
            members_offset + 32 + i * 32 : members_offset + 64 + i * 32
        ][-20:].hex()
        for i in range(members_length)
    ]
    return {
        "activation_block": int.from_bytes(word(0), "big"),
        "keyper_set": "0x" + word(1)[-20:].hex(),
        "members": members,
        "threshold": int.from_bytes(word(3), "big"),
        "eon": int.from_bytes(word(4), "big"),
    }


def require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{label} mismatch: actual={actual!r}, expected={expected!r}"
        )


def certificate_status(row: dict[str, Any]) -> str:
    """Return a certificate only when period-matched floor evidence was audited."""
    if not row.get("period_evidence_audited", False):
        return MISSING_PERIOD_EVIDENCE
    threshold = row.get("threshold")
    resistance_count = row.get("positive_resistance_floors")
    if threshold in ("", None) or resistance_count in ("", None):
        return MISSING_PERIOD_EVIDENCE
    if int(resistance_count) < int(threshold):
        return ZERO_PUBLIC_FLOOR_CERTIFICATE
    return "REQUIRES_MEMBER_LEVEL_FLOOR_VALUES"


def find_matching_event(
    rpc: RpcClient,
    config: dict[str, Any],
    set_id: int,
    set_address: str,
    activation_block: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    lookback = int(config.get("event_search_lookback_blocks", 250_000))
    chunk_size = int(config.get("rpc_log_chunk_blocks", 10_000))
    forward_blocks = int(config.get("event_search_forward_blocks", 100))
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []

    # Set 0 on the retained Gnosis deployment is a boundary case: its
    # KeyperSetAdded event was emitted one block after its activation block.
    # Search a small forward window before walking backwards in chunks.
    forward_to = min(
        int(config["snapshot_block"]),
        activation_block + forward_blocks,
    )
    forward_logs = rpc.call(
        "eth_getLogs",
        [{
            "address": config["manager_address"],
            "fromBlock": hex(activation_block),
            "toBlock": hex(forward_to),
            "topics": [config["keyper_set_added_topic0"]],
        }],
    )
    for log in forward_logs:
        event = decode_keyper_set_added(log["data"])
        if (
            event["eon"] == set_id
            and event["keyper_set"].lower() == set_address.lower()
        ):
            matches.append((log, event))

    searched = 0
    while searched < lookback and not matches:
        width = min(chunk_size, lookback - searched)
        to_block = activation_block - 1 - searched
        from_block = max(0, to_block - width + 1)
        params = [{
            "address": config["manager_address"],
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "topics": [config["keyper_set_added_topic0"]],
        }]
        logs = rpc.call("eth_getLogs", params)
        for log in logs:
            event = decode_keyper_set_added(log["data"])
            if (
                event["eon"] == set_id
                and event["keyper_set"].lower() == set_address.lower()
            ):
                matches.append((log, event))
        searched += width
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one KeyperSetAdded event for set {set_id}, "
            f"found {len(matches)} from {lookback} blocks before activation "
            f"through {forward_blocks} blocks after activation; adjust the "
            "event search bounds if necessary"
        )
    return matches[0]


def load_live_sets(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict]:
    required = [
        "rpc_url",
        "manager_address",
        "snapshot_block",
        "snapshot_block_hash",
        "chain_id",
        "keyper_set_added_topic0",
    ]
    missing = [key for key in required if config.get(key) in ("", None)]
    if missing:
        raise ValueError(
            "Live audit requires full configuration values: " + ", ".join(missing)
        )

    rpc = RpcClient(
        config["rpc_url"],
        max_attempts=int(config.get("rpc_max_attempts", 4)),
        timeout_seconds=int(config.get("rpc_timeout_seconds", 45)),
        retry_base_seconds=int(config.get("rpc_retry_base_seconds", 2)),
    )
    chain_id = int(rpc.call("eth_chainId", []), 16)
    require_equal("chain id", chain_id, int(config["chain_id"]))

    snapshot_block = int(config["snapshot_block"])
    block_tag = hex(snapshot_block)
    block = rpc.call("eth_getBlockByNumber", [block_tag, False])
    require_equal("snapshot block number", int(block["number"], 16), snapshot_block)
    require_equal(
        "snapshot block hash",
        block["hash"].lower(),
        config["snapshot_block_hash"].lower(),
    )

    manager = config["manager_address"]
    num_sets = decode_uint(
        rpc.eth_call(manager, SELECTORS["getNumKeyperSets"], block_tag)
    )
    active_index = decode_uint(
        rpc.eth_call(
            manager,
            SELECTORS["getKeyperSetIndexByBlock"] + encode_uint(snapshot_block),
            block_tag,
        )
    )
    if "expected_num_keyper_sets" in config:
        require_equal(
            "number of keyper sets",
            num_sets,
            int(config["expected_num_keyper_sets"]),
        )
    if "expected_active_set_index" in config:
        require_equal(
            "active keyper set index",
            active_index,
            int(config["expected_active_set_index"]),
        )

    retained_evidence = config.get("retained_period_evidence", {})
    retained_set_id = retained_evidence.get("set_id")
    manager_calls = []
    for set_id in range(num_sets):
        manager_calls.extend([
            (
                manager,
                SELECTORS["getKeyperSetAddress"] + encode_uint(set_id),
            ),
            (
                manager,
                SELECTORS["getKeyperSetActivationBlock"] + encode_uint(set_id),
            ),
        ])
    manager_results = rpc.batch_eth_call(manager_calls, block_tag)
    set_descriptors = [
        (
            decode_address(manager_results[2 * set_id]),
            decode_uint(manager_results[2 * set_id + 1]),
        )
        for set_id in range(num_sets)
    ]

    rows: list[dict[str, Any]] = []
    for set_id in range(num_sets):
        set_address, activation_block = set_descriptors[set_id]
        state_results = rpc.batch_eth_call(
            [
                (set_address, SELECTORS["getMembers"]),
                (set_address, SELECTORS["getNumMembers"]),
                (set_address, SELECTORS["getThreshold"]),
                (set_address, SELECTORS["getPublisher"]),
                (set_address, SELECTORS["owner"]),
                (set_address, SELECTORS["isFinalized"]),
            ],
            block_tag,
        )
        members = decode_address_array(state_results[0])
        member_count = decode_uint(state_results[1])
        threshold = decode_uint(state_results[2])
        publisher = decode_address(state_results[3])
        owner = decode_address(state_results[4])
        finalized = decode_bool(state_results[5])
        require_equal(f"set {set_id} member count", len(members), member_count)

        log, event = find_matching_event(
            rpc, config, set_id, set_address, activation_block
        )
        require_equal(
            f"set {set_id} event activation",
            event["activation_block"],
            activation_block,
        )
        require_equal(f"set {set_id} event threshold", event["threshold"], threshold)
        require_equal(
            f"set {set_id} event members",
            [member.lower() for member in event["members"]],
            [member.lower() for member in members],
        )

        has_period_evidence = retained_set_id is not None and int(
            retained_set_id
        ) == set_id
        row = {
            "set_id": set_id,
            "address": set_address,
            "start_block": activation_block,
            "end_block": snapshot_block,
            "member_count": member_count,
            "threshold": threshold,
            "members": "|".join(members),
            "owner": owner,
            "publisher": publisher,
            "finalized": finalized,
            "event_block": int(log["blockNumber"], 16),
            "event_tx": log["transactionHash"],
            "event_verified": True,
            "committee_state_verified": True,
            "period_evidence_audited": has_period_evidence,
            "positive_resistance_floors": (
                int(retained_evidence["positive_resistance_floors"])
                if has_period_evidence
                else ""
            ),
            "positive_activation_floors": (
                int(retained_evidence["positive_activation_floors"])
                if has_period_evidence
                else ""
            ),
            "positive_penalty_floors": (
                int(retained_evidence["positive_penalty_floors"])
                if has_period_evidence
                else ""
            ),
            "source": (
                "live_rpc_plus_retained_period_evidence"
                if has_period_evidence
                else "live_rpc_committee_state_only"
            ),
        }
        row["certificate_status"] = certificate_status(row)
        rows.append(row)
        print(
            f"set {set_id}/{num_sets - 1} verified: "
            f"activation={activation_block}, "
            f"event={row['event_block']}, "
            f"members={member_count}, threshold={threshold}",
            flush=True,
        )

    for index in range(len(rows) - 1):
        rows[index]["end_block"] = rows[index + 1]["start_block"] - 1

    metadata = {
        "chain_id": chain_id,
        "snapshot_block": snapshot_block,
        "snapshot_block_hash": block["hash"],
        "active_set_index": active_index,
    }
    return rows, metadata


def load_fixture_sets(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict]:
    rows = []
    for fixture in config["fixture_sets"]:
        row = dict(fixture)
        row.setdefault("period_evidence_audited", True)
        row.setdefault("event_verified", False)
        row.setdefault("committee_state_verified", True)
        row["certificate_status"] = certificate_status(row)
        rows.append(row)
    return rows, {
        "chain_id": config.get("chain_id"),
        "snapshot_block": config.get("snapshot_block"),
        "snapshot_block_hash": config.get("snapshot_block_hash"),
        "active_set_index": config.get("expected_active_set_index"),
    }


def summarize(
    rows: list[dict[str, Any]], mode: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    committee_verified = sum(
        bool(row.get("committee_state_verified")) for row in rows
    )
    events_verified = sum(bool(row.get("event_verified")) for row in rows)
    evidence_audited = sum(bool(row.get("period_evidence_audited")) for row in rows)
    zero_sets = sum(
        row.get("certificate_status") == ZERO_PUBLIC_FLOOR_CERTIFICATE
        for row in rows
    )
    missing_evidence = sum(
        row.get("certificate_status") == MISSING_PERIOD_EVIDENCE for row in rows
    )
    live_longitudinal = (
        mode == "live"
        and len(rows) >= 2
        and committee_verified == len(rows)
        and events_verified == len(rows)
    )
    return {
        "mode": mode,
        **metadata,
        "sets_audited": len(rows),
        "committee_states_verified": committee_verified,
        "events_verified": events_verified,
        "period_evidence_sets_audited": evidence_audited,
        "missing_period_evidence_sets": missing_evidence,
        "zero_public_floor_certificate_sets": zero_sets,
        "supports_longitudinal_committee_claim": live_longitudinal,
        "supports_longitudinal_certificate_claim": False,
        "persistent_zero_across_observed_sets": None,
        "scope": (
            "multi_set_live_committee_history"
            if mode == "live"
            else "single_pinned_snapshot_fixture"
        ),
        "interpretation": (
            "Committee address, rotation span, membership, threshold, and "
            "KeyperSetAdded event are independently checked by live RPC. "
            "A period receives a certificate only when period-matched public "
            "floor evidence was separately audited. Missing evidence is not zero."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.live:
        rows, metadata = load_live_sets(config)
        prefix = "historical_keyper_sets"
        mode = "live"
    else:
        rows, metadata = load_fixture_sets(config)
        prefix = "pinned_snapshot_audit"
        mode = "fixture"

    ensure_results()
    fields = [
        "set_id",
        "address",
        "start_block",
        "end_block",
        "member_count",
        "threshold",
        "members",
        "owner",
        "publisher",
        "finalized",
        "event_block",
        "event_tx",
        "event_verified",
        "committee_state_verified",
        "period_evidence_audited",
        "positive_resistance_floors",
        "positive_activation_floors",
        "positive_penalty_floors",
        "certificate_status",
        "source",
    ]
    normalized_rows = [{field: row.get(field, "") for field in fields} for row in rows]
    write_csv(RESULTS / f"{prefix}.csv", normalized_rows, fields)
    write_json(RESULTS / f"{prefix}.json", {"sets": normalized_rows})
    write_json(RESULTS / f"{prefix}_summary.json", summarize(rows, mode, metadata))


if __name__ == "__main__":
    main()
