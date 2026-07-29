#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "results" / "phase1_scenarios.json"
CONTRACT_PATH = ROOT / "contracts" / "TraceThenSlash.sol"

BOND = 2 * 10**18
REWARD = 10**17
THRESHOLD = 4
EXPECTED_FLOOR = THRESHOLD * BOND
EXPECTED_REWARD = THRESHOLD * REWARD
EXPECTED_TREASURY = EXPECTED_FLOOR - EXPECTED_REWARD
EXPECTED_GROUPINGS = {
    "sequential": [1, 1, 1, 1],
    "atomic_package": [4],
    "repeated_packages": [2, 2],
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


data = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
require(data["schema"] == "fc-trace-then-slash-phase1-v1", "bad result schema")
require(data["rq"] == "RQ2", "wrong research question")
require(data["environment"]["independentOperators"] is False, "scope drift")
require(data["environment"]["productionDeployment"] is False, "scope drift")
require(data["certificate"]["status"] == "POSITIVE_SCOPED", "not a positive scoped certificate")
require(int(data["certificate"]["lowerBoundWei"]) == EXPECTED_FLOOR, "wrong lower bound")
require(data["coverage"]["packageSizeParameterB"] == "not used", "external b reintroduced")
require(
    data["coverage"]["acceptedAtomicPackageSizes"] == list(range(1, 8)),
    "finite package coverage is incomplete",
)
require(data["coverage"]["repeatedPackages"] is True, "repeated packages not covered")
require(data["coverage"]["silentOffProtocolTransfers"] is False, "silent-transfer overclaim")

source_hash = hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()
require(data["contractSourceSha256"] == source_hash, "contract source hash mismatch")

scenarios = {item["mode"]: item for item in data["scenarios"]}
require(set(scenarios) == set(EXPECTED_GROUPINGS), "scenario set mismatch")
for mode, grouping in EXPECTED_GROUPINGS.items():
    scenario = scenarios[mode]
    require(scenario["grouping"] == grouping, f"{mode}: grouping mismatch")
    require(scenario["slashedMemberIndices"] == [0, 1, 2, 3], f"{mode}: member set mismatch")
    require(int(scenario["initialTotalBondWei"]) == 7 * BOND, f"{mode}: total bond mismatch")
    require(
        int(scenario["preAttackThresholdBondFloorWei"]) == EXPECTED_FLOOR,
        f"{mode}: pre-attack floor mismatch",
    )
    require(
        int(scenario["realizedMemberLossWei"]) == EXPECTED_FLOOR,
        f"{mode}: realized member loss mismatch",
    )
    require(
        int(scenario["callerRewardAccruedWei"]) == EXPECTED_REWARD,
        f"{mode}: caller reward mismatch",
    )
    require(
        int(scenario["treasuryAccruedWei"]) == EXPECTED_TREASURY,
        f"{mode}: treasury accrual mismatch",
    )
    require(int(scenario["remainingBondWei"]) == 3 * BOND, f"{mode}: remaining bond mismatch")
    require(
        int(scenario["postAttackCurrentCertificateWei"]) == 0,
        f"{mode}: post-attack certificate must expose committee exhaustion",
    )
    require(len(scenario["transactions"]) == len(grouping), f"{mode}: transaction count mismatch")
    require(
        all(tx["status"] == "success" and int(tx["gasUsed"]) > 0 for tx in scenario["transactions"]),
        f"{mode}: failed or empty transaction record",
    )

print("PHASE1_CERTIFICATE=POSITIVE_SCOPED")
print(f"LOWER_BOUND_WEI={EXPECTED_FLOOR}")
print("SEQUENTIAL_ATOMIC_REPEATED_EQUIVALENCE=PASS")
print("CALLER_REWARD_ACCRUAL=PASS")
print("NO_EXTERNAL_PACKAGE_BOUND_B=PASS")
print("SCOPE_GUARDS=PASS")
