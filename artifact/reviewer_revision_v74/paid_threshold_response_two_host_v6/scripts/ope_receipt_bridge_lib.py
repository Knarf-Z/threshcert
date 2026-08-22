"""Bind the OPE payment receipt to the existing threshold-response service.

The contract does not carry a secret share.  Instead, its ordered member
indices are bound, once, to the already-dealt threshold operators by public
Schnorr attestations.  A successful receipt then selects exactly those
operators; the normal HTTP response, network-signature, Chaum--Pedersen, and
threshold-reconstruction path is reused unchanged.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from ptr_v3.experiment import Committee
from ptr_v3.network_identity import (
    NetworkIdentity,
    OperatorRegistry,
    SchnorrSignature,
    sign,
    verify,
)
from ptr_v3.utils import canonical_json_bytes, read_json, sha256_hex


BRIDGE_SCHEMA = "ptr-ope-receipt-bridge/v1"
BINDING_SCHEMA = "ptr-ope-member-binding/v1"


class ReceiptBridgeError(ValueError):
    """A receipt or identity binding failed closed."""


def _lower(value: object) -> str:
    return str(value).lower()


def _mask(indices: list[int]) -> int:
    result = 0
    for index in indices:
        result |= 1 << index
    return result


def _binding_statement(
    *,
    receipt: Mapping[str, Any],
    committee: Committee,
    registry: OperatorRegistry,
    member_index: int,
    operator_id: int,
    member_address: str,
    host_id: str,
    network_public_key: int,
) -> dict[str, object]:
    return {
        "schema": BINDING_SCHEMA,
        "chain_id": int(receipt["chain_id"]),
        "contract_address": str(receipt["contract"]["address"]),
        "contract_runtime_bytecode_keccak256": str(
            receipt["contract"]["runtime_bytecode_keccak256"]
        ),
        "committee_registry_digest": registry.digest(),
        "member_index": member_index,
        "member_address": member_address,
        "operator_id": operator_id,
        "host_id": host_id,
        "network_public_key": hex(network_public_key),
        "threshold": committee.threshold,
        "committee_size": committee.committee_size,
    }


def build_operator_bindings(
    receipt: Mapping[str, Any],
    committee: Committee,
    secret_root: Path,
) -> dict[str, object]:
    """Create public binding attestations from the existing operator secrets.

    This is a setup/ceremony operation.  The returned object contains only
    public statements and signatures; threshold and network secret material is
    never serialized into the bridge result.
    """

    registry = OperatorRegistry.from_public(committee.operator_hosts, committee.network_public_keys)
    addresses = [str(value) for value in receipt["committee_member_addresses"]]
    if len(addresses) != committee.committee_size:
        raise ReceiptBridgeError("receipt committee size does not match the dealt committee")

    entries: list[dict[str, object]] = []
    for member_index, member_address in enumerate(addresses):
        operator_id = member_index + 1
        host_id = committee.operator_hosts[operator_id]
        secret_path = secret_root / host_id / f"operator-{operator_id}.secret.json"
        secret = read_json(secret_path)
        if int(secret["operator_id"]) != operator_id:
            raise ReceiptBridgeError(f"secret file is for the wrong operator: {secret_path}")
        identity = NetworkIdentity.from_secret(
            operator_id,
            host_id,
            int(str(secret["network_secret_key"]), 16),
        )
        if identity.public_key != committee.network_public_keys[operator_id]:
            raise ReceiptBridgeError(f"network identity mismatch for operator {operator_id}")
        statement = _binding_statement(
            receipt=receipt,
            committee=committee,
            registry=registry,
            member_index=member_index,
            operator_id=operator_id,
            member_address=member_address,
            host_id=host_id,
            network_public_key=identity.public_key,
        )
        signature = sign(identity, canonical_json_bytes(statement))
        entries.append({**statement, "signature": signature.to_dict()})
    return {
        "schema": BINDING_SCHEMA,
        "registry_digest": registry.digest(),
        "entries": entries,
    }


def verify_operator_bindings(
    receipt: Mapping[str, Any],
    committee: Committee,
    binding: Mapping[str, Any],
) -> list[dict[str, object]]:
    registry = OperatorRegistry.from_public(committee.operator_hosts, committee.network_public_keys)
    if binding.get("schema") != BINDING_SCHEMA or binding.get("registry_digest") != registry.digest():
        raise ReceiptBridgeError("operator binding schema or registry digest mismatch")
    entries = list(binding.get("entries", []))
    addresses = [str(value) for value in receipt["committee_member_addresses"]]
    if len(entries) != committee.committee_size or len(addresses) != committee.committee_size:
        raise ReceiptBridgeError("operator binding does not cover the full committee")

    checked: list[dict[str, object]] = []
    for expected_index, raw in enumerate(entries):
        entry = dict(raw)
        signature = SchnorrSignature.from_dict(dict(entry.pop("signature")))
        operator_id = int(entry.get("operator_id", -1))
        member_index = int(entry.get("member_index", -1))
        if member_index != expected_index or operator_id != member_index + 1:
            raise ReceiptBridgeError("member index to operator id mapping was substituted")
        if _lower(entry.get("member_address")) != _lower(addresses[member_index]):
            raise ReceiptBridgeError("member address differs from the on-chain receipt")
        public_key = registry.public_key(operator_id)
        if public_key is None or entry.get("network_public_key") != hex(public_key):
            raise ReceiptBridgeError("binding does not match the public operator registry")
        if entry.get("host_id") != registry.host_of(operator_id):
            raise ReceiptBridgeError("binding host differs from the operator registry")
        if not verify(public_key, canonical_json_bytes(entry), signature):
            raise ReceiptBridgeError(f"operator {operator_id} binding signature does not verify")
        checked.append({**entry, "signature": signature.to_dict()})
    return checked


def verify_receipt(
    receipt: Mapping[str, Any],
    committee: Committee,
    binding: Mapping[str, Any],
) -> dict[str, object]:
    """Verify the exact successful payment and return the selected operators."""

    payment = dict(receipt.get("payment_transaction", {}))
    state = dict(receipt.get("ope_state_after_payment", {}))
    contract = dict(receipt.get("contract", {}))
    if receipt.get("schema") != "ope-receipt-bridge-capture/v1":
        raise ReceiptBridgeError("unsupported OPE receipt schema")
    if payment.get("status") != "success" or not state.get("configured") or not state.get("completed"):
        raise ReceiptBridgeError("receipt is not a successful completed OPE execution")
    if _lower(payment.get("to")) != _lower(contract.get("address")):
        raise ReceiptBridgeError("payment destination is not the OPE contract")
    buyer = _lower(payment.get("from"))
    members = [_lower(value) for value in receipt.get("committee_member_addresses", [])]
    if not buyer or buyer in members:
        raise ReceiptBridgeError("payment buyer is not an external acquirer")
    if _lower(state.get("acquirer")) != buyer:
        raise ReceiptBridgeError("OPE acquirer does not equal the payment sender")
    if int(payment.get("value_wei", -1)) != int(state.get("quote_wei", -2)):
        raise ReceiptBridgeError("payment value differs from the contract quote")
    if int(payment.get("value_wei", -1)) != int(state.get("total_acquisition_call_value_wei", -2)):
        raise ReceiptBridgeError("payment value differs from the recorded acquisition value")

    selected_indices = [int(value) for value in state.get("selected_member_indices", [])]
    if len(selected_indices) != committee.threshold or selected_indices != sorted(set(selected_indices)):
        raise ReceiptBridgeError("receipt selected-member set is not an ordered threshold set")
    expected_mask = _mask(selected_indices)
    if int(state.get("delivered_share_mask", -1)) != expected_mask or int(state.get("terminal_mask", -1)) != expected_mask:
        raise ReceiptBridgeError("delivered mask does not match the selected member set")

    checked_bindings = verify_operator_bindings(receipt, committee, binding)
    selected_operator_ids = [int(checked_bindings[index]["operator_id"]) for index in selected_indices]
    return {
        "buyer": buyer,
        "contract_address": str(contract["address"]),
        "contract_runtime_bytecode_keccak256": str(contract["runtime_bytecode_keccak256"]),
        "payment_tx_hash": str(payment["hash"]),
        "payment_block_number": str(payment["block_number"]),
        "payment_value_wei": str(payment["value_wei"]),
        "selected_member_indices": selected_indices,
        "selected_operator_ids": selected_operator_ids,
        "selected_mask": hex(expected_mask),
        "registry_digest": str(binding["registry_digest"]),
        "binding_entries": checked_bindings,
    }


def expect_receipt_rejection(receipt: Mapping[str, Any], committee: Committee, binding: Mapping[str, Any]) -> str:
    try:
        verify_receipt(receipt, committee, binding)
    except ReceiptBridgeError as error:
        return str(error)
    raise AssertionError("mutated receipt was accepted")


def negative_receipt_cases(
    receipt: Mapping[str, Any],
    committee: Committee,
    binding: Mapping[str, Any],
) -> dict[str, object]:
    cases: dict[str, Mapping[str, Any]] = {}

    underpayment = deepcopy(receipt)
    underpayment["payment_transaction"]["value_wei"] = str(int(receipt["payment_transaction"]["value_wei"]) - 1)
    cases["underpayment"] = underpayment

    wrong_buyer = deepcopy(receipt)
    wrong_buyer["payment_transaction"]["from"] = "0x0000000000000000000000000000000000000001"
    cases["wrong_buyer"] = wrong_buyer

    mask_substitution = deepcopy(receipt)
    mask_substitution["ope_state_after_payment"]["delivered_share_mask"] ^= 1
    cases["mask_substitution"] = mask_substitution

    substituted_binding = deepcopy(binding)
    substituted_binding["entries"][0]["operator_id"] = 2
    cases["operator_substitution"] = {**receipt, "_binding_override": substituted_binding}

    outcomes: dict[str, object] = {}
    for name, mutated in cases.items():
        candidate_binding = mutated.pop("_binding_override", binding) if isinstance(mutated, dict) else binding
        try:
            verify_receipt(mutated, committee, candidate_binding)
        except ReceiptBridgeError as error:
            outcomes[name] = {"rejected": True, "reason": str(error)}
        else:
            outcomes[name] = {"rejected": False, "reason": "unexpected acceptance"}
    return outcomes


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(receipt))

