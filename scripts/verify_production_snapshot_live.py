#!/usr/bin/env python3
"""Recheck the pinned production committee against a Gnosis archival RPC.

This optional network check uses only the Python standard library.  The root
deterministic reproduction command does not require network access.
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = ROOT / "data" / "production_keyper_set_20260613.json"

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


class RpcClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.identifier = 0

    def call(self, method: str, params: list[Any]) -> Any:
        self.identifier += 1
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": self.identifier,
                "method": method,
                "params": params,
            }
        ).encode()
        request = urllib.request.Request(
            self.url, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
        if "error" in result:
            raise RuntimeError(f"RPC {method} failed: {result['error']}")
        return result["result"]

    def eth_call(self, address: str, data: str, block_tag: str) -> str:
        return self.call("eth_call", [{"to": address, "data": data}, block_tag])


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
    raw = bytes.fromhex(data[2:])
    word = lambda index: raw[index * 32 : (index + 1) * 32]
    members_offset = int.from_bytes(word(2), "big")
    members_length = int.from_bytes(raw[members_offset : members_offset + 32], "big")
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
        "threshold": int.from_bytes(word(3), "big"),
        "eon": int.from_bytes(word(4), "big"),
        "members": members,
    }


def require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise SystemExit(f"{label} mismatch: actual={actual!r}, expected={expected!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--rpc", default=None)
    args = parser.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    rpc_url = args.rpc or record["rpc_provenance"]["endpoint"]
    rpc = RpcClient(rpc_url)
    anchor = record["audit_anchor"]
    manager = record["manager"]
    keyper_set = record["keyper_set"]
    block_tag = hex(anchor["block_number"])

    block = rpc.call("eth_getBlockByNumber", [block_tag, False])
    require_equal("block number", int(block["number"], 16), anchor["block_number"])
    require_equal("block hash", block["hash"].lower(), anchor["block_hash"].lower())
    require_equal("block timestamp", int(block["timestamp"], 16), anchor["timestamp"])

    manager_address = manager["address"]
    num_sets = decode_uint(
        rpc.eth_call(manager_address, SELECTORS["getNumKeyperSets"], block_tag)
    )
    index_data = SELECTORS["getKeyperSetIndexByBlock"] + encode_uint(
        anchor["block_number"]
    )
    index = decode_uint(rpc.eth_call(manager_address, index_data, block_tag))
    set_data = SELECTORS["getKeyperSetAddress"] + encode_uint(index)
    set_address = decode_address(rpc.eth_call(manager_address, set_data, block_tag))
    activation_data = SELECTORS["getKeyperSetActivationBlock"] + encode_uint(index)
    activation_block = decode_uint(
        rpc.eth_call(manager_address, activation_data, block_tag)
    )
    require_equal("number of sets", num_sets, manager["num_keyper_sets"])
    require_equal("active set index", index, manager["active_keyper_set_index"])
    require_equal("set address", set_address.lower(), keyper_set["address"].lower())
    require_equal("activation block", activation_block, keyper_set["activation_block"])

    address = keyper_set["address"]
    members = decode_address_array(
        rpc.eth_call(address, SELECTORS["getMembers"], block_tag)
    )
    num_members = decode_uint(
        rpc.eth_call(address, SELECTORS["getNumMembers"], block_tag)
    )
    threshold = decode_uint(
        rpc.eth_call(address, SELECTORS["getThreshold"], block_tag)
    )
    publisher = decode_address(
        rpc.eth_call(address, SELECTORS["getPublisher"], block_tag)
    )
    finalized = decode_bool(
        rpc.eth_call(address, SELECTORS["isFinalized"], block_tag)
    )
    owner = decode_address(rpc.eth_call(address, SELECTORS["owner"], block_tag))
    require_equal("member count", num_members, keyper_set["num_members"])
    require_equal("threshold", threshold, keyper_set["threshold"])
    require_equal(
        "members",
        [member.lower() for member in members],
        [member.lower() for member in keyper_set["members"]],
    )
    require_equal("publisher", publisher.lower(), keyper_set["publisher"].lower())
    require_equal("finalized", finalized, keyper_set["finalized"])
    require_equal("owner", owner.lower(), keyper_set["owner"].lower())

    added_receipt = rpc.call(
        "eth_getTransactionReceipt", [manager["keyper_set_added_transaction"]]
    )
    require_equal("set-added receipt status", int(added_receipt["status"], 16), 1)
    require_equal(
        "set-added block", int(added_receipt["blockNumber"], 16), manager["keyper_set_added_block"]
    )
    matching_logs = [
        log
        for log in added_receipt["logs"]
        if log["address"].lower() == manager_address.lower()
        and log["topics"][0].lower() == manager["keyper_set_added_event_topic0"].lower()
    ]
    require_equal("KeyperSetAdded log count", len(matching_logs), 1)
    event = decode_keyper_set_added(matching_logs[0]["data"])
    require_equal("event activation block", event["activation_block"], activation_block)
    require_equal("event set address", event["keyper_set"].lower(), address.lower())
    require_equal("event threshold", event["threshold"], threshold)
    require_equal("event eon", event["eon"], index)
    require_equal(
        "event members",
        [member.lower() for member in event["members"]],
        [member.lower() for member in members],
    )

    creation_receipt = rpc.call(
        "eth_getTransactionReceipt", [keyper_set["creation_transaction"]]
    )
    require_equal("creation receipt status", int(creation_receipt["status"], 16), 1)
    require_equal(
        "created contract",
        creation_receipt["contractAddress"].lower(),
        address.lower(),
    )
    require_equal(
        "creation block",
        int(creation_receipt["blockNumber"], 16),
        keyper_set["creation_block"],
    )

    print(f"production_snapshot_block={anchor['block_number']}")
    print(f"production_snapshot_hash={anchor['block_hash']}")
    print(f"keyper_set_index={index}")
    print(f"keyper_set_contract={address}")
    print(f"committee_members={num_members}")
    print(f"threshold={threshold}")
    print("keyper_set_event=VERIFIED")
    print("keyper_set_creation=VERIFIED")
    print("production_snapshot_live_verification=PASS")


if __name__ == "__main__":
    main()
