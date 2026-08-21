"""Independent finite-world verifier for the global named-acquirer toy instance."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable


HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "model.v1.json"
RESULTS = HERE / "results"
CERTIFICATE_PATH = RESULTS / "global_named_acquirer_certificate.v1.json"
LOG_PATH = RESULTS / "global_named_acquirer_certificate.v1.log"
ZERO = 0


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def exact_keys(value: dict, keys: set[str], label: str) -> None:
    actual = set(value)
    if actual != keys:
        raise ValueError(f"{label} keys differ: missing={sorted(keys-actual)} extra={sorted(actual-keys)}")


@dataclass(frozen=True, order=True)
class State:
    opened: bool = False
    accepted_a: bool = False
    accepted_b: bool = False
    successful: bool = False
    output_usable: bool = False
    buyer: int = 10_000_000_000_000_000_000
    exchange: int = 0
    member_a: int = 0
    member_b: int = 0
    credit_a: int = 0
    credit_b: int = 0


def apply_action(state: State, action: str, g: int, amount_a: int, amount_b: int) -> State | None:
    if action == "open":
        if state.opened or state.buyer < g:
            return None
        return replace(state, opened=True, buyer=state.buyer - g, exchange=state.exchange + g)
    if action == "submit_a":
        if not state.opened or state.accepted_a or state.successful:
            return None
        if state.accepted_b:
            return replace(
                state,
                accepted_a=True,
                successful=True,
                output_usable=True,
                credit_a=amount_a,
                credit_b=amount_b,
            )
        return replace(state, accepted_a=True)
    if action == "submit_b":
        if not state.opened or state.accepted_b or state.successful:
            return None
        if state.accepted_a:
            return replace(
                state,
                accepted_b=True,
                successful=True,
                output_usable=True,
                credit_a=amount_a,
                credit_b=amount_b,
            )
        return replace(state, accepted_b=True)
    if action == "withdraw_a":
        if state.credit_a == 0 or state.exchange < state.credit_a:
            return None
        return replace(
            state,
            exchange=state.exchange - state.credit_a,
            member_a=state.member_a + state.credit_a,
            credit_a=0,
        )
    if action == "withdraw_b":
        if state.credit_b == 0 or state.exchange < state.credit_b:
            return None
        return replace(
            state,
            exchange=state.exchange - state.credit_b,
            member_b=state.member_b + state.credit_b,
            credit_b=0,
        )
    raise ValueError(f"unknown action {action}")


def enumerate_states(actions: tuple[str, ...], g: int, amount_a: int, amount_b: int) -> tuple[set[State], set[tuple[str, ...]], list[tuple[State, str, State]]]:
    initial = State()
    reachable = {initial}
    frontier = [initial]
    transitions: list[tuple[State, str, State]] = []
    while frontier:
        state = frontier.pop(0)
        for action in actions:
            nxt = apply_action(state, action, g, amount_a, amount_b)
            if nxt is None:
                continue
            transitions.append((state, action, nxt))
            if nxt not in reachable:
                reachable.add(nxt)
                frontier.append(nxt)

    successful_routes: set[tuple[str, ...]] = set()

    def visit(state: State, route: tuple[str, ...]) -> None:
        if state.successful:
            successful_routes.add(route)
            return
        for action in actions:
            nxt = apply_action(state, action, g, amount_a, amount_b)
            if nxt is not None:
                visit(nxt, (*route, action))

    visit(initial, ())
    return reachable, successful_routes, transitions


def validate_model(model: dict) -> tuple[int, int, int, tuple[str, ...], set[tuple[str, ...]]]:
    exact_keys(model, {"schema", "claim", "worldClosure", "mechanism", "evmBinding"}, "model")
    if model["schema"] != "global-named-acquirer-toy-world/v1":
        raise ValueError("unexpected model schema")
    claim = model["claim"]
    closure = model["worldClosure"]
    mechanism = model["mechanism"]
    binding = model["evmBinding"]
    exact_keys(claim, {"namedAcquirer", "accountingUnit", "certifiedFloor", "window", "successPredicate"}, "claim")
    exact_keys(
        closure,
        {
            "finite",
            "accounts",
            "controlEdges",
            "namedAcquirerControlClosure",
            "initialBalances",
            "externalFundingEvents",
            "returnOrReimbursementEvents",
            "mechanismUniverseComplete",
        },
        "worldClosure",
    )
    exact_keys(
        mechanism,
        {"actions", "openDebit", "memberCredits", "successfulRoutes", "buyerRefundAction", "bypassSuccessAction"},
        "mechanism",
    )
    exact_keys(binding, {"source", "test", "compiledArtifact", "evidence", "transcript"}, "evmBinding")

    if claim["namedAcquirer"] != "buyer" or claim["accountingUnit"] != "simulated-wei":
        raise ValueError("claim identity or unit mismatch")
    if claim["window"] != [0, 5]:
        raise ValueError("window mismatch")
    if closure["finite"] is not True or closure["mechanismUniverseComplete"] is not True:
        raise ValueError("world is not declared finite and complete")
    if closure["accounts"] != ["buyer", "exchange", "member_a", "member_b"]:
        raise ValueError("account universe mismatch")
    if closure["controlEdges"] != [] or closure["namedAcquirerControlClosure"] != ["buyer"]:
        raise ValueError("control closure is not the explicit buyer singleton")
    if closure["externalFundingEvents"] != [] or closure["returnOrReimbursementEvents"] != []:
        raise ValueError("base world has funding or return events")
    if closure["initialBalances"] != {
        "buyer": "10000000000000000000",
        "exchange": "0",
        "member_a": "0",
        "member_b": "0",
    }:
        raise ValueError("initial balance vector mismatch")
    if mechanism["buyerRefundAction"] is not None or mechanism["bypassSuccessAction"] is not None:
        raise ValueError("base world contains a refund or bypass")

    actions = tuple(mechanism["actions"])
    if actions != ("open", "submit_a", "submit_b", "withdraw_a", "withdraw_b"):
        raise ValueError("action universe mismatch")
    g = int(claim["certifiedFloor"])
    if g != int(mechanism["openDebit"]):
        raise ValueError("claim floor and open debit differ")
    amount_a = int(mechanism["memberCredits"]["member_a"])
    amount_b = int(mechanism["memberCredits"]["member_b"])
    if amount_a + amount_b != g:
        raise ValueError("member credits do not conserve the debit")
    expected_routes = {tuple(route) for route in mechanism["successfulRoutes"]}
    return g, amount_a, amount_b, actions, expected_routes


def validate_evm(model: dict) -> dict:
    paths = {key: (HERE / rel).resolve() for key, rel in model["evmBinding"].items()}
    for label, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing {label}: {path}")
    evidence = load_json(paths["evidence"])
    exact_keys(
        evidence,
        {"schema", "status", "fullSuitePassing", "namedTestCases", "inputs", "compiledRuntime", "transcript"},
        "evm evidence",
    )
    if evidence["schema"] != "global-named-acquirer-toy-evm/v1" or evidence["status"] != "PASS":
        raise ValueError("bad EVM evidence status")
    if evidence["fullSuitePassing"] != 18 or evidence["namedTestCases"] != 6:
        raise ValueError("unexpected EVM test counts")
    if evidence["inputs"] != {
        "sourceSha256": digest(paths["source"]),
        "testSha256": digest(paths["test"]),
        "compiledArtifactSha256": digest(paths["compiledArtifact"]),
    }:
        raise ValueError("EVM evidence input hash mismatch")
    if evidence["transcript"] != {
        "path": "results/global_named_acquirer_toy_evm.log",
        "sha256": digest(paths["transcript"]),
    }:
        raise ValueError("EVM transcript mismatch")

    artifact = load_json(paths["compiledArtifact"])
    runtime = bytes.fromhex(artifact["deployedBytecode"][2:])
    if evidence["compiledRuntime"] != {"bytes": len(runtime), "sha256": hashlib.sha256(runtime).hexdigest()}:
        raise ValueError("compiled runtime mismatch")
    opcodes: list[int] = []
    cursor = 0
    while cursor < len(runtime):
        opcode = runtime[cursor]
        opcodes.append(opcode)
        cursor += 1
        if 0x60 <= opcode <= 0x7F:
            cursor += opcode - 0x5F
    forbidden = {0xF0: "CREATE", 0xF2: "CALLCODE", 0xF4: "DELEGATECALL", 0xF5: "CREATE2", 0xFF: "SELFDESTRUCT"}
    present = sorted(name for opcode, name in forbidden.items() if opcode in opcodes)
    if present:
        raise ValueError(f"forbidden executable opcodes: {present}")
    if any(item.get("type") in {"fallback", "receive"} for item in artifact["abi"]):
        raise ValueError("ABI contains fallback or receive entry")
    function_names = sorted(item["name"] for item in artifact["abi"] if item.get("type") == "function")
    required = {
        "CERTIFIED_OUTFLOW", "MEMBER_A_AMOUNT", "MEMBER_B_AMOUNT", "acceptedA", "acceptedB", "buyer",
        "credit", "expectedShareA", "expectedShareB", "memberA", "memberB", "open", "opened", "resourceId",
        "submitShare", "successful", "usableOutputCommitment", "withdrawCredit",
    }
    if set(function_names) != required:
        raise ValueError(f"ABI closure mismatch: {function_names}")
    return evidence


@dataclass(frozen=True)
class Variant:
    usable_output: bool = True
    external_funding: int = 0
    debit_before_output: bool = True
    return_to_closure: int = 0
    bypass_success: bool = False


def evaluate_variant(variant: Variant, g: int) -> dict:
    debit = 0 if variant.bypass_success else g
    outflow = max(0, debit - variant.external_funding - variant.return_to_closure)
    gates = {
        "B1": variant.usable_output,
        "B2": variant.external_funding == 0,
        "B3": variant.debit_before_output,
        "B4": variant.return_to_closure == 0,
        "B5": not variant.bypass_success,
    }
    failed = [name for name in ("B1", "B2", "B3", "B4", "B5") if not gates[name]]
    if variant.usable_output and outflow < g:
        verdict = "MODEL-REFUTED"
    elif failed:
        verdict = "UNKNOWN"
    else:
        verdict = "CERTIFIED"
    return {"gates": gates, "failedGates": failed, "outflow": outflow, "verdict": verdict}


def negative_controls(g: int, amount_a: int) -> list[dict]:
    specs = [
        ("missing_usable_output", Variant(usable_output=False), "B1", "UNKNOWN"),
        ("outside_sponsor_funds_exact_debit", Variant(external_funding=g), "B2", "MODEL-REFUTED"),
        ("output_precedes_irreversible_debit", Variant(debit_before_output=False), "B3", "UNKNOWN"),
        ("buyer_receives_complete_return", Variant(return_to_closure=g), "B4", "MODEL-REFUTED"),
        ("member_a_added_to_buyer_control_closure", Variant(return_to_closure=amount_a), "B4", "MODEL-REFUTED"),
        ("unlisted_zero_debit_success_bypass", Variant(bypass_success=True), "B5", "MODEL-REFUTED"),
    ]
    records = []
    for name, variant, expected_gate, expected_verdict in specs:
        observed = evaluate_variant(variant, g)
        observed_gate = observed["failedGates"][0] if observed["failedGates"] else None
        status = "PASS" if observed_gate == expected_gate and observed["verdict"] == expected_verdict else "FAIL"
        records.append(
            {
                "name": name,
                "mutation": asdict(variant),
                "expectedFailedGate": expected_gate,
                "observedFailedGate": observed_gate,
                "expectedVerdict": expected_verdict,
                "observedVerdict": observed["verdict"],
                "observedOutflow": str(observed["outflow"]),
                "status": status,
            }
        )
    return records


def interface_ablations(g: int) -> list[dict]:
    variants = [
        ("outside sponsor supplies the five-unit debit", Variant(external_funding=g)),
        ("five units return to the buyer after local success", Variant(return_to_closure=g)),
    ]
    records = []
    for case, variant in variants:
        observed = evaluate_variant(variant, g)
        if observed["outflow"] != 0 or observed["verdict"] != "MODEL-REFUTED":
            raise ValueError(f"interface ablation failed: {case}")
        records.append(
            {
                "case": case,
                "mutation": asdict(variant),
                "naiveLocalEqualsGlobal": f"CERTIFIED({g})",
                "typedGlobalOutflow": str(observed["outflow"]),
                "typedVerdict": f"{observed['verdict']}({g})",
            }
        )
    return records


def build_certificate(model: dict) -> dict:
    g, amount_a, amount_b, actions, expected_routes = validate_model(model)
    evm = validate_evm(model)
    reachable, routes, transitions = enumerate_states(actions, g, amount_a, amount_b)
    if routes != expected_routes:
        raise ValueError(f"B5 route closure mismatch: expected={expected_routes} actual={routes}")
    successful_states = [state for state in reachable if state.successful]
    if not successful_states or any(not state.output_usable for state in successful_states):
        raise ValueError("B1 usable-output relation failed")
    if any(state.buyer != State().buyer - g for state in successful_states):
        raise ValueError("B2 named-acquirer debit failed")
    if any(nxt.buyer > state.buyer for state, _, nxt in transitions):
        raise ValueError("B4 value returned to buyer")
    if any(state.exchange + state.member_a + state.member_b + state.buyer != State().buyer for state in reachable):
        raise ValueError("conservation failed")
    for route in routes:
        if route[0] != "open" or route[-1] not in {"submit_a", "submit_b"}:
            raise ValueError("B3 debit-before-output order failed")

    controls = negative_controls(g, amount_a)
    if any(
        item["status"] != "PASS"
        or item["expectedFailedGate"] != item["observedFailedGate"]
        or item["expectedVerdict"] != item["observedVerdict"]
        for item in controls
    ):
        raise ValueError("negative-control expectation failed")
    binding = {key: (HERE / rel).resolve() for key, rel in model["evmBinding"].items()}
    route_records = [
        {
            "actions": list(route),
            "boundaryDebit": str(g),
            "externalFunding": "0",
            "returnsOrReimbursement": "0",
            "netNamedAcquirerOutflow": str(g),
            "usableOutput": True,
        }
        for route in sorted(routes)
    ]
    return {
        "schema": "global-named-acquirer-certificate/v1",
        "status": "PASS",
        "verdict": f"GLOBAL-NAMED-ACQUIRER-CERTIFIED({g})",
        "scope": "complete finite declared toy world only; not an Internet-wide or production-control claim",
        "claim": model["claim"],
        "gates": {
            "B1": {"status": "PASS", "evidence": "both fixed share commitments imply a nonzero buyer/resource-bound output commitment"},
            "B2": {"status": "PASS", "evidence": "buyer starts with 10e18 units, pays 5e18, and the complete action universe has no funding action"},
            "B3": {"status": "PASS", "evidence": "every first-success trace starts with the irreversible open debit"},
            "B4": {"status": "PASS", "evidence": "singleton buyer control closure; no refund, reimbursement, circular return, or buyer credit transition"},
            "B5": {"status": "PASS", "evidence": "all enabled actions enumerated; exactly two first-success routes match the supplied route inventory"},
        },
        "enumeration": {
            "reachableStates": len(reachable),
            "enabledTransitions": len(transitions),
            "firstSuccessRoutes": len(routes),
            "routeRecords": route_records,
        },
        "evm": evm,
        "interfaceAblation": interface_ablations(g),
        "negativeControls": controls,
        "inputs": {
            "modelSha256": digest(MODEL_PATH),
            "sourceSha256": digest(binding["source"]),
            "testSha256": digest(binding["test"]),
            "compiledArtifactSha256": digest(binding["compiledArtifact"]),
            "evmEvidenceSha256": digest(binding["evidence"]),
            "evmTranscriptSha256": digest(binding["transcript"]),
            "verifierSha256": digest(Path(__file__).resolve()),
        },
    }


def canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def log_text(certificate: dict) -> str:
    enum = certificate["enumeration"]
    return "\n".join(
        [
            "GLOBAL_NAMED_ACQUIRER_TOY=PASS",
            f"VERDICT={certificate['verdict']}",
            "B1=PASS B2=PASS B3=PASS B4=PASS B5=PASS",
            f"REACHABLE_STATES={enum['reachableStates']}",
            f"ENABLED_TRANSITIONS={enum['enabledTransitions']}",
            f"FIRST_SUCCESS_ROUTES={enum['firstSuccessRoutes']}",
            f"NEGATIVE_CONTROLS={len(certificate['negativeControls'])}/6",
            "INTERFACE_ABLATION=2/2 MODEL-REFUTED",
            "SCOPE=COMPLETE_FINITE_DECLARED_TOY_WORLD_ONLY",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    model = load_json(MODEL_PATH)
    certificate = build_certificate(model)
    encoded = canonical_bytes(certificate)
    log = log_text(certificate)
    if args.self_test and any(control["status"] != "PASS" for control in certificate["negativeControls"]):
        raise SystemExit("negative controls failed")
    if args.write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        CERTIFICATE_PATH.write_bytes(encoded)
        LOG_PATH.write_text(log, encoding="utf-8", newline="\n")
    else:
        if CERTIFICATE_PATH.read_bytes() != encoded:
            raise SystemExit("committed global certificate differs from independent replay")
        if LOG_PATH.read_text(encoding="utf-8") != log:
            raise SystemExit("committed global certificate log differs from replay")
    print(log, end="")


if __name__ == "__main__":
    main()
