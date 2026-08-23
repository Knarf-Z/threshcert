from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from longitudinal_audit import (
    MISSING_PERIOD_EVIDENCE,
    ZERO_PUBLIC_FLOOR_CERTIFICATE,
    certificate_status,
    decode_keyper_set_added,
    find_matching_event,
    summarize,
)


def abi_word(value: int) -> bytes:
    return value.to_bytes(32, "big")


def abi_address(value: str) -> bytes:
    return bytes.fromhex(value[2:]).rjust(32, b"\0")


def encoded_event(
    activation_block: int,
    set_address: str,
    members: list[str],
    threshold: int,
    eon: int,
) -> str:
    head = b"".join([
        abi_word(activation_block),
        abi_address(set_address),
        abi_word(5 * 32),
        abi_word(threshold),
        abi_word(eon),
    ])
    tail = abi_word(len(members)) + b"".join(abi_address(x) for x in members)
    return "0x" + (head + tail).hex()


def test_decode_keyper_set_added() -> None:
    set_address = "0x1111111111111111111111111111111111111111"
    members = [
        "0x2222222222222222222222222222222222222222",
        "0x3333333333333333333333333333333333333333",
    ]
    decoded = decode_keyper_set_added(
        encoded_event(1234, set_address, members, 2, 7)
    )
    assert decoded == {
        "activation_block": 1234,
        "keyper_set": set_address,
        "members": members,
        "threshold": 2,
        "eon": 7,
    }


def test_decode_rejects_truncated_event() -> None:
    with pytest.raises(ValueError, match="shorter"):
        decode_keyper_set_added("0x" + bytes(32).hex())


def test_missing_period_evidence_is_not_zero() -> None:
    assert certificate_status({
        "period_evidence_audited": False,
        "threshold": 4,
        "positive_resistance_floors": 0,
    }) == MISSING_PERIOD_EVIDENCE


def test_audited_insufficient_public_floors_produce_zero_certificate() -> None:
    assert certificate_status({
        "period_evidence_audited": True,
        "threshold": 4,
        "positive_resistance_floors": 0,
    }) == ZERO_PUBLIC_FLOOR_CERTIFICATE


def test_summary_separates_committee_and_certificate_claims() -> None:
    rows = [
        {
            "committee_state_verified": True,
            "event_verified": True,
            "period_evidence_audited": False,
            "certificate_status": MISSING_PERIOD_EVIDENCE,
        },
        {
            "committee_state_verified": True,
            "event_verified": True,
            "period_evidence_audited": True,
            "certificate_status": ZERO_PUBLIC_FLOOR_CERTIFICATE,
        },
    ]
    result = summarize(
        rows,
        "live",
        {
            "chain_id": 100,
            "snapshot_block": 10,
            "snapshot_block_hash": "0xabc",
            "active_set_index": 1,
        },
    )
    assert result["supports_longitudinal_committee_claim"] is True
    assert result["supports_longitudinal_certificate_claim"] is False
    assert result["persistent_zero_across_observed_sets"] is None
    assert result["missing_period_evidence_sets"] == 1
    assert result["zero_public_floor_certificate_sets"] == 1


def test_event_one_block_after_activation_is_found() -> None:
    set_address = "0x1111111111111111111111111111111111111111"
    member = "0x2222222222222222222222222222222222222222"
    activation_block = 1234
    log = {
        "data": encoded_event(
            activation_block,
            set_address,
            [member],
            1,
            0,
        ),
        "blockNumber": hex(activation_block + 1),
        "transactionHash": "0xabc",
    }

    class FakeRpc:
        def call(self, method: str, params: list) -> list[dict]:
            assert method == "eth_getLogs"
            query = params[0]
            if int(query["fromBlock"], 16) == activation_block:
                return [log]
            return []

    found_log, event = find_matching_event(
        FakeRpc(),  # type: ignore[arg-type]
        {
            "snapshot_block": 2000,
            "manager_address": "0x3333333333333333333333333333333333333333",
            "keyper_set_added_topic0": "0xtopic",
            "event_search_forward_blocks": 100,
            "event_search_lookback_blocks": 250000,
            "rpc_log_chunk_blocks": 10000,
        },
        0,
        set_address,
        activation_block,
    )
    assert found_log["blockNumber"] == hex(activation_block + 1)
    assert event["eon"] == 0
