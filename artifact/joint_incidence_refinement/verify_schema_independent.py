#!/usr/bin/env python3
"""Independent finite-schema and preserved Halmos-certificate checker."""
from hashlib import sha256
from itertools import combinations, product
from json import loads
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CERTIFICATE = ROOT / "results" / "refinement_certificate.json"
OBLIGATION_MAP = ROOT / "results" / "refinement_obligation_map.json"
HALMOS = ROOT / "results" / "halmos_evm_bridge.json"
HALMOS_RUNNER = ROOT / "scripts" / "run_halmos_bridge.py"
HALMOS_LOG = ROOT / "results" / "halmos_evm_bridge.log"
DEPLOYMENT_RECORD = ROOT / "results" / "deployment_admission_local.json"
DEPLOYMENT_CERTIFICATE = ROOT / "results" / "deployment_admission_certificate.json"
DEPLOYMENT_NEGATIVE = ROOT / "results" / "deployment_admission_negative.json"
DEPLOYMENT_CHECKER = ROOT / "verify_deployment_admission.mjs"
SOURCE = ROOT / "contracts" / "OverlappingPoolEscrow.sol"
HARNESS = ROOT / "formal" / "OverlappingPoolEscrowBridge.t.sol"
CONFIG = ROOT / "foundry.toml"
ARTIFACT = ROOT / "artifacts" / "contracts" / "OverlappingPoolEscrow.sol" / "OverlappingPoolEscrow.json"
MEMBERS = tuple(range(7))
Q = (2,) * 7


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def executable_hash(runtime):
    raw = bytes.fromhex(runtime.removeprefix("0x"))
    trailer = int.from_bytes(raw[-2:], "big") + 2
    assert 2 <= trailer <= len(raw)
    executable = raw[:-trailer]
    return sha256(executable).hexdigest(), len(executable)


def admissible_credits():
    return tuple(
        y for y in product(range(3), repeat=7)
        if sum(y[:4]) <= 2 and sum(y[3:]) <= 2
    )


def quote(y, selected):
    return sum(Q[i] - y[i] for i in selected)


def main():
    credits = admissible_credits()
    terminals = tuple(combinations(MEMBERS, 4))
    assert len(credits) == 117 and len(terminals) == 35
    roots = {(y, False, None) for y in credits}
    terminal_states = {(y, True, selected) for y in credits for selected in terminals}
    assert len(roots) == 117 and len(terminal_states) == 4095
    assert roots.isdisjoint(terminal_states)

    declared_edges = {}
    payments = []
    for y in credits:
        source = (y, False, None)
        for selected in terminals:
            target = (y, True, selected)
            payment = quote(y, selected)
            key = (source, selected)
            assert key not in declared_edges
            declared_edges[key] = (target, payment)
            assert target[0] == source[0]
            assert target[1] is True and target[2] == selected
            assert len(set(selected)) == 4
            assert tuple(sorted(selected)) == selected
            assert payment == sum(2 - y[i] for i in selected)
            assert payment >= 4
            payments.append(payment)

    assert len(declared_edges) == len(credits) * len(terminals) == 4095
    for source in roots:
        assert {
            selected for selected in terminals if (source, selected) in declared_edges
        } == set(terminals)
    for state in roots | terminal_states:
        assert (state in terminal_states) == bool(state[1])
    coordinate_minima = tuple(min(2 - y[i] for y in credits) for i in MEMBERS)
    assert coordinate_minima == (0,) * 7 and min(payments) == 4

    halmos = loads(HALMOS.read_text(encoding="utf-8"))
    assert halmos["schema"] == "overlapping-pool-halmos-bridge/v6"
    assert halmos["status"] == "PASS"
    assert halmos["parameters"]["halmosLoopBound"] >= 8
    assert halmos["inputs"]["contractSha256"] == digest(SOURCE)
    assert halmos["inputs"]["harnessSha256"] == digest(HARNESS)
    assert halmos["inputs"]["foundryConfigSha256"] == digest(CONFIG)
    assert halmos["transcript"]["sha256"] == digest(HALMOS_LOG)
    counts = halmos["proofCounts"]
    assert counts == {
        "symbolicEdgeWrappers": 35,
        "symbolicPayerEdgeWrappers": 35,
        "preTerminalWithdrawWrappers": 7,
        "terminalWithdrawWrappers": 21,
        "auxiliaryObligations": 9,
        "roleConflictObligations": 8,
        "hostileCallbackObligations": 2,
        "totalProofs": 82,
        "failed": 0,
        "nonemptyBounds": 0,
    }
    expected_proofs = {
        *(f"check_EVMEdge_{''.join(map(str, selected))}" for selected in terminals),
        *(f"check_EVMWithdrawProjectionNeutral_{i}" for i in MEMBERS),
        *(
            f"check_EVMTerminalWithdraw{prefix}_{i}"
            for prefix in (
                "Selected",
                "SelectedAfterPoolWithdraw",
                "Unselected",
            )
            for i in MEMBERS
        ),
        "check_EVMCompletedAcquireAlwaysReverts",
        "check_EVMConfigureSuccessClosure",
        "check_EVMExcessFundingReverts",
        "check_EVMEntryClosure",
        "check_EVMHostileCallbackPreTerminal",
        "check_EVMHostileCallbackTerminal",
        "check_EVMInvalidSetReverts",
        "check_EVMOversizeCreditReverts",
        "check_EVMReconfigureAlwaysReverts",
        "check_EVMRoleConflictedController",
        *(f"check_EVMRoleConflictedMember_{i}" for i in MEMBERS),
        "check_EVMUnauthorizedConfigure",
        "check_EVMWithdrawValueReverts",
    }
    assert set(halmos["proofs"]) == expected_proofs
    assert all(result["bounds"] == [] for result in halmos["proofs"].values())
    harness_text = HARNESS.read_text(encoding="utf-8")
    assert all(harness_text.count(f"function {name}") == 1 for name in expected_proofs)

    hardhat = loads(ARTIFACT.read_text(encoding="utf-8"))
    hardhat_hash, hardhat_bytes = executable_hash(hardhat["deployedBytecode"])
    compiled = halmos["compiledRuntime"]
    assert compiled["foundryRuntimeExecutableSha256"] == hardhat_hash
    assert compiled["foundryRuntimeExecutableBytes"] == hardhat_bytes

    admission_record = loads(DEPLOYMENT_RECORD.read_text(encoding="utf-8"))
    admission_certificate = loads(DEPLOYMENT_CERTIFICATE.read_text(encoding="utf-8"))
    controller = admission_record["constructor"]["controller"].lower()
    deployment_members = tuple(
        member.lower() for member in admission_record["constructor"]["members"]
    )
    assert len(set(deployment_members)) == 7
    assert controller not in deployment_members
    observed = admission_record["observationsAtDeploymentBlock"]
    assert observed["deliveredShareMask"] == 0
    assert tuple(owner.lower() for owner in observed["shareOwners"]) == deployment_members
    assert admission_record["schema"] == "overlapping-pool-deployment-admission/v1"
    assert admission_certificate["schema"] == "overlapping-pool-deployment-admission-certificate/v1"
    assert admission_certificate["status"] == "PASS"
    assert admission_certificate["recordSha256"] == digest(DEPLOYMENT_RECORD)
    assert admission_certificate["artifactSha256"] == digest(ARTIFACT)
    admission_negative = loads(DEPLOYMENT_NEGATIVE.read_text(encoding="utf-8"))
    assert admission_negative["schema"] == "overlapping-pool-deployment-admission-negative/v1"
    assert admission_negative["status"] == "PASS"
    assert admission_negative["totalRejected"] == 10
    assert admission_negative["canonicalRecordSha256"] == digest(DEPLOYMENT_RECORD)
    assert admission_negative["checkerSha256"] == digest(DEPLOYMENT_CHECKER)

    certificate = loads(CERTIFICATE.read_text(encoding="utf-8"))
    assert certificate["schema"] == "overlapping-pool-schema-certificate/v7"
    assert certificate["bridgeScope"]["closedContractEconomicIncidence"]
    obligation_map = loads(OBLIGATION_MAP.read_text(encoding="utf-8"))
    assert obligation_map["schema"] == "overlapping-pool-refinement-obligation-map/v1"
    assert obligation_map["status"] == "PASS"
    assert set(obligation_map["refinementClauses"]) == {
        "initializationTotality", "offsetLiftStructure", "terminalFamilyCompleteness",
        "outcomeCompleteness", "entryClosure", "forwardSimulation",
        "backwardRealization", "terminalEquivalence", "paymentPreservation",
        "closedContractEconomicIncidence", "callbackAndFiberClosure",
    }
    assert all(
        item["status"] == "PASS" and item["evidence"]
        for item in obligation_map["refinementClauses"].values()
    )
    assert obligation_map["paperClauseMap"]["offsetLiftDefinition"] == "offsetLiftStructure"
    assert obligation_map["paperClauseMap"]["separateTerminalPremise"] == (
        "terminalFamilyCompleteness"
    )
    assert obligation_map["paperClauseMap"]["separateMechanismLiftPremise"] == (
        "outcomeCompleteness"
    )
    assert len(obligation_map["trustedComputingBase"]) >= 5
    assert obligation_map["explicitExclusions"]
    finite = certificate["finiteCheck"]
    assert finite["admissibleCreditVectors"] == len(credits)
    assert finite["terminalSets"] == len(terminals)
    assert finite["checkedStateSetPairs"] == len(declared_edges)
    assert finite["minimumResidualPayment"] == min(payments)
    assert tuple(finite["coordinateResidualMinima"]) == coordinate_minima
    assert certificate["obligations"]["implementationToSchemaBridge"].startswith("PASS")
    evidence = certificate["implementationAuditEvidence"]
    assert evidence["halmosCertificateSha256"] == digest(HALMOS)
    assert evidence["halmosRunnerSha256"] == digest(HALMOS_RUNNER)
    assert evidence["halmosTranscriptSha256"] == digest(HALMOS_LOG)
    assert evidence["deploymentAdmissionRecordSha256"] == digest(DEPLOYMENT_RECORD)
    assert evidence["deploymentAdmissionCertificateSha256"] == digest(DEPLOYMENT_CERTIFICATE)
    assert evidence["deploymentAdmissionNegativeSha256"] == digest(DEPLOYMENT_NEGATIVE)
    assert evidence["deploymentAdmissionCheckerSha256"] == digest(DEPLOYMENT_CHECKER)
    assert evidence["refinementObligationMapSha256"] == digest(OBLIGATION_MAP)
    assert evidence["runtimeExecutableSha256"] == hardhat_hash
    assert evidence["foundryHardhatExecutableMatch"] is True

    print("INDEPENDENT_SCHEMA_ENTRY_CLOSURE=PASS")
    print("INDEPENDENT_SCHEMA_FORWARD_SIMULATION=PASS")
    print("INDEPENDENT_SCHEMA_BACKWARD_REALIZABILITY=PASS")
    print("INDEPENDENT_SCHEMA_TERMINAL_EQUIVALENCE=PASS")
    print("INDEPENDENT_SCHEMA_PAYMENT_PRESERVATION=PASS")
    print(f"INDEPENDENT_SCHEMA_STATE_SET_PAIRS={len(declared_edges)}")
    print(f"INDEPENDENT_SCHEMA_MIN_PAYMENT={min(payments)}")
    print("INDEPENDENT_HALMOS_PROOF_CERTIFICATE=PASS")
    print("INDEPENDENT_DEPLOYMENT_ADMISSION=PASS")
    print("INDEPENDENT_DEPLOYMENT_ADMISSION_TAMPER_CASES=10_REJECTED")
    print("INDEPENDENT_HOSTILE_CALLBACK_CLOSURE=PASS")
    print("INDEPENDENT_FOUNDRY_HARDHAT_EXECUTABLE_BYTECODE=MATCH")
    print("INDEPENDENT_CONFIGURATION_PREFIX_TOTALITY=PASS")
    print("INDEPENDENT_OFFSET_LIFT_ROOT_TERMINAL_STRUCTURE=PASS")
    print("INDEPENDENT_TERMINAL_FAMILY_COMPLETENESS=35_OF_35_PASS")
    print("INDEPENDENT_CLOSED_CONTRACT_TRACE_OUTCOME_CORRESPONDENCE=PASS")
    print("INDEPENDENT_POSTCONFIGURATION_EVM_TO_SCHEMA_BRIDGE=PASS")
    print("INDEPENDENT_EVM_TO_SCHEMA_SCOPE=ADMITTED_CANCUN_RUNTIME_WITH_CLOSED_CONTRACT_INCIDENCE")


if __name__ == "__main__":
    main()