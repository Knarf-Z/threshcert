#!/usr/bin/env python3
"""Build or verify the machine-readable certificate for the recorded Chiado run.

The certificate is intentionally narrow.  It binds the recorded Rolling Shutter
evidence, public Chiado transactions, and exact four-smallest-bonds calculation.
It does not turn the controlled single-host testnet run into a production
Shutter resistance or activation certificate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE_PATH = ROOT / "certificates" / "chiado-execution-certificate.json"
SCHEMA = "fc-chiado-execution-certificate-v1"
DOMAIN_SEPARATOR = b"fc-chiado-execution-certificate-v1\x00"
SOURCE_PATHS = (
    "contracts/BondedKeyperSlasher.sol",
    "evidence/shutter-evidence.json",
    "results/deployment-chiado.json",
    "results/job-chiado.json",
    "results/slashing-chiado.json",
    "rolling-shutter/evidence-exporter/main.go",
    "rolling-shutter/evidence-exporter/main_test.go",
    "runtime/keyper-set.json",
    "scripts/verify-chiado-live.ts",
)


def fail(message: str) -> None:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"{relative} must contain a JSON object")
    return value


def sha256_file(relative: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_address(value: Any, label: str) -> str:
    require(isinstance(value, str), f"{label} must be a string")
    require(len(value) == 42 and value.startswith("0x"), f"{label} is not an address")
    return value.lower()


def integer(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    require(result >= 0, f"{label} must be nonnegative")
    return result


def indexed_addresses(items: Any, index_field: str, address_field: str, label: str) -> list[str]:
    require(isinstance(items, list), f"{label} must be a list")
    ordered = sorted(items, key=lambda item: integer(item[index_field], f"{label} index"))
    indices = [integer(item[index_field], f"{label} index") for item in ordered]
    require(indices == list(range(len(ordered))), f"{label} indices are not contiguous")
    addresses = [
        normalized_address(item[address_field], f"{label}[{index}].{address_field}")
        for index, item in enumerate(ordered)
    ]
    require(len(addresses) == len(set(addresses)), f"{label} addresses are not unique")
    return addresses


def threshold_cover(bonds: list[int], threshold: int) -> int:
    require(0 < threshold <= len(bonds), "invalid threshold for bond vector")
    return sum(sorted(bonds)[:threshold])


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_certificate() -> dict[str, Any]:
    deployment = load_json("results/deployment-chiado.json")
    job = load_json("results/job-chiado.json")
    evidence = load_json("evidence/shutter-evidence.json")
    slashing = load_json("results/slashing-chiado.json")
    keyper_set = load_json("runtime/keyper-set.json")

    require(deployment.get("schema") == "fc-bonded-keyper-deployment-v1", "bad deployment schema")
    require(job.get("schema") == "fc-release-job-v1", "bad job schema")
    require(evidence.get("schema") == "fc-shutter-evidence-v1", "bad evidence schema")
    require(slashing.get("schema") == "fc-slashing-result-v1", "bad slashing schema")
    require(keyper_set.get("schema") == "fc-keyper-set-v1", "bad Keyper-set schema")

    chain_id = integer(deployment.get("chainId"), "deployment chainId")
    require(chain_id == 10200, "recorded deployment is not on Gnosis Chiado")
    require(integer(job.get("chainId"), "job chainId") == chain_id, "job chain mismatch")
    require(integer(slashing.get("chainId"), "slashing chainId") == chain_id, "slashing chain mismatch")

    contract = normalized_address(deployment.get("contract"), "deployment contract")
    require(normalized_address(job.get("contract"), "job contract") == contract, "job contract mismatch")
    require(
        normalized_address(slashing.get("contract"), "slashing contract") == contract,
        "slashing contract mismatch",
    )

    committee_size = integer(deployment.get("committeeSize"), "committeeSize")
    threshold = integer(deployment.get("threshold"), "threshold")
    require((committee_size, threshold) == (7, 4), "certificate requires the recorded 4-of-7 committee")
    require(integer(keyper_set.get("threshold"), "Keyper-set threshold") == threshold, "Keyper-set threshold mismatch")
    require(integer(evidence.get("threshold"), "evidence threshold") == threshold, "evidence threshold mismatch")
    require(integer(evidence.get("numKeypers"), "evidence numKeypers") == committee_size, "evidence committee mismatch")

    deployment_addresses = indexed_addresses(deployment.get("keypers"), "index", "address", "deployment keypers")
    keyper_set_addresses = indexed_addresses(keyper_set.get("keypers"), "index", "address", "exported Keyper set")
    share_addresses = indexed_addresses(evidence.get("shares"), "memberIndex", "keyperAddress", "evidence shares")
    require(len(deployment_addresses) == committee_size, "deployment Keyper count mismatch")
    require(deployment_addresses == keyper_set_addresses == share_addresses, "Keyper identities do not align")

    shares = sorted(evidence["shares"], key=lambda item: integer(item["memberIndex"], "share memberIndex"))
    require(all(item.get("shareValid") is True for item in shares), "not every BLS share is marked valid")
    require(
        all(item.get("nativeSignatureValid") is True for item in shares),
        "not every native Keyper signature is marked valid",
    )
    require(evidence.get("aggregateKeyValid") is True, "aggregate key was not validated")
    require(
        evidence.get("reconstructionMatchesStoredKey") is True,
        "four-share reconstruction does not match the stored key",
    )
    require(
        evidence.get("rollingShutterVersion") == keyper_set.get("rollingShutterVersion") == "v1.4.4",
        "Rolling Shutter version mismatch",
    )
    require(
        evidence.get("rollingShutterCommit") == keyper_set.get("rollingShutterCommit"),
        "Rolling Shutter commit mismatch",
    )
    require(str(job.get("eon")) == str(evidence.get("eon")), "job/evidence eon mismatch")
    require(job.get("identityHash") == evidence.get("identityHash"), "identity hash mismatch")
    require(job.get("identityPreimage") == evidence.get("identityPreimage"), "identity preimage mismatch")
    require(job.get("jobId") == slashing.get("jobId"), "job identifier mismatch")

    slashed_index = integer(slashing.get("memberIndex"), "slashed member index")
    require(slashed_index < committee_size, "slashed member index is out of range")
    slashed_share = shares[slashed_index]
    require(
        normalized_address(slashing.get("keyperAddress"), "slashed Keyper")
        == normalized_address(slashed_share.get("keyperAddress"), "share Keyper"),
        "slashed Keyper mismatch",
    )
    require(slashing.get("shareHash") == slashed_share.get("shareHash"), "slashed share hash mismatch")
    require(
        slashing.get("memberSignatureHash") == slashed_share.get("nativeSignatureHash"),
        "slashed native-signature hash mismatch",
    )
    require(
        normalized_address(slashing.get("verifier"), "slashing verifier")
        == normalized_address(deployment.get("verifier"), "deployment verifier"),
        "verifier mismatch",
    )

    release_time = integer(job.get("releaseTime"), "releaseTime")
    observed_at = integer(slashing.get("observedAt"), "observedAt")
    premature_by = integer(slashing.get("prematureBySeconds"), "prematureBySeconds")
    require(observed_at < release_time, "share was not recorded before the release time")
    require(release_time - observed_at == premature_by, "prematurity interval mismatch")

    deployment_transactions = [deployment["transactions"]["deploy"]]
    deployment_transactions.extend(deployment["transactions"]["registrations"])
    deployment_transactions.append(deployment["transactions"]["freeze"])
    all_transactions = deployment_transactions + [job["transaction"], slashing["transaction"]]
    require(len(deployment_transactions) == 9, "deployment transaction count mismatch")
    require(len(all_transactions) == 11, "public transaction count mismatch")
    require(all(item.get("status") == "success" for item in all_transactions), "a recorded transaction failed")
    transaction_hashes = [item.get("hash") for item in all_transactions]
    require(len(transaction_hashes) == len(set(transaction_hashes)), "transaction hashes are not unique")

    bond = integer(deployment.get("bondWeiPerMember"), "bondWeiPerMember")
    total_bond = integer(deployment.get("totalBondWei"), "totalBondWei")
    require(total_bond == committee_size * bond, "total bond does not equal seven member bonds")
    before_bonds = [bond] * committee_size
    after_bonds = before_bonds.copy()
    after_bonds[slashed_index] = 0
    before_value = threshold_cover(before_bonds, threshold)
    after_value = threshold_cover(after_bonds, threshold)
    require(
        integer(deployment.get("initialCertificateWei"), "initialCertificateWei") == before_value,
        "deployment certificate does not match the lower-tail calculation",
    )
    require(
        integer(slashing.get("certificateBeforeWei"), "certificateBeforeWei") == before_value,
        "pre-slashing certificate mismatch",
    )
    require(
        integer(slashing.get("certificateAfterWei"), "certificateAfterWei") == after_value,
        "post-slashing certificate mismatch",
    )

    slashing_transaction = slashing["transaction"]
    source_digests = {relative: sha256_file(relative) for relative in SOURCE_PATHS}
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "certificateClass": "controlled-public-testnet-threshold-cover",
        "claim": {
            "status": "POSITIVE_WITHIN_RECORDED_TESTNET_MECHANISM",
            "statement": (
                "At the recorded Chiado state, the instrumented 4-of-7 contract's "
                "sum-of-four-smallest-live-bonds value is 3000000000000 wei."
            ),
            "unconditionalProductionAttackCostLowerBound": None,
            "productionShutterCertificate": "NOT_CERTIFIED",
            "productionMemberResistance": "NOT_CERTIFIED",
            "productionActivationEvidence": "NOT_CERTIFIED",
            "deploymentWideEnforcementProbability": "NOT_CERTIFIED",
        },
        "scope": {
            "networkName": deployment.get("networkName"),
            "chainId": chain_id,
            "contract": deployment.get("contract"),
            "recordedBlockNumber": slashing_transaction.get("blockNumber"),
            "recordedBlockHash": slashing_transaction.get("blockHash"),
            "committeeSize": committee_size,
            "threshold": threshold,
            "keyperProcessModel": "seven-colocated-processes-on-one-host",
            "mechanism": "verifier-attested early-share slashing with on-chain bond transfer",
            "certificateInput": (
                "remaining on-chain testnet bond balances under the covered "
                "verifier-gated enforcement path"
            ),
            "coveredExecutionConditions": [
                "the pinned exporter detects and validates a premature share",
                "the designated verifier issues the field-bound EIP-712 attestation",
                "the attestation reaches the contract before the recorded release deadline",
            ],
        },
        "certificate": {
            "formula": "sum_of_q_smallest_live_bonds",
            "unit": "wei",
            "before": {
                "memberBounds": [str(value) for value in before_bonds],
                "value": str(before_value),
            },
            "after": {
                "memberBounds": [str(value) for value in after_bonds],
                "value": str(after_value),
            },
        },
        "observedEvidence": {
            "rollingShutterVersion": evidence.get("rollingShutterVersion"),
            "rollingShutterCommit": evidence.get("rollingShutterCommit"),
            "eon": str(evidence.get("eon")),
            "jobId": job.get("jobId"),
            "releaseTime": str(release_time),
            "observedAt": str(observed_at),
            "prematureBySeconds": str(premature_by),
            "validatedShares": len(shares),
            "validNativeSignatures": sum(item.get("nativeSignatureValid") is True for item in shares),
            "aggregateKeyValid": True,
            "fourShareReconstructionMatches": True,
            "slashedMemberIndex": slashed_index,
            "slashingTransaction": {
                "hash": slashing_transaction.get("hash"),
                "blockNumber": slashing_transaction.get("blockNumber"),
                "blockHash": slashing_transaction.get("blockHash"),
                "status": slashing_transaction.get("status"),
            },
            "recordedTransactionCount": len(all_transactions),
        },
        "verification": {
            "offlineCommand": "python scripts/verify_chiado_certificate.py",
            "liveChainCommand": "npm run verify:chiado:live",
            "liveChainVerificationRequiredForPublicChainClaim": True,
            "sourceDigestsSha256": source_digests,
        },
    }
    certificate_id = hashlib.sha256(DOMAIN_SEPARATOR + canonical_json(payload)).hexdigest()
    return {"certificateId": f"sha256:{certificate_id}", **payload}


def verify_stored_certificate(expected: dict[str, Any]) -> None:
    require(CERTIFICATE_PATH.is_file(), f"missing certificate: {CERTIFICATE_PATH.relative_to(ROOT)}")
    with CERTIFICATE_PATH.open(encoding="utf-8") as handle:
        actual = json.load(handle)
    require(actual == expected, "stored Chiado execution certificate is stale or inconsistent")


def print_summary(certificate: dict[str, Any]) -> None:
    evidence = certificate["observedEvidence"]
    value = certificate["certificate"]
    print(f"certificate_id={certificate['certificateId']}")
    print(f"certificate_class={certificate['certificateClass']}")
    print(f"chain_id={certificate['scope']['chainId']}")
    print(f"contract={certificate['scope']['contract']}")
    print(f"threshold={certificate['scope']['threshold']}-of-{certificate['scope']['committeeSize']}")
    print(f"validated_shares={evidence['validatedShares']}")
    print(f"recorded_transactions={evidence['recordedTransactionCount']}")
    print(f"certificate_before_wei={value['before']['value']}")
    print(f"certificate_after_wei={value['after']['value']}")
    print("offline_evidence_binding=PASS")
    print("production_shutter_certificate=NOT_CERTIFIED")
    print("chiado_execution_certificate=PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the deterministic certificate before verifying it",
    )
    args = parser.parse_args()

    try:
        certificate = build_certificate()
        if args.write:
            CERTIFICATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CERTIFICATE_PATH.write_text(
                json.dumps(certificate, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        verify_stored_certificate(certificate)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"chiado_execution_certificate=FAIL: {exc}") from exc

    print_summary(certificate)


if __name__ == "__main__":
    main()
