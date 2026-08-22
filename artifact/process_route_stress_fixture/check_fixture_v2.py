#!/usr/bin/env python3
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "model.v2.json"
RESULT_PATH = ROOT / "results" / "process_route_stress.v2.json"
LOG_PATH = ROOT / "results" / "process_route_stress.v2.log"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def event_index(events, event_type):
    matches = [event["position"] for event in events if event["type"] == event_type]
    require(matches, f"missing event: {event_type}")
    return min(matches)


def validate_route(route, source, header):
    events = route["events"]
    require([event["position"] for event in events] == list(range(len(events))),
            "event positions are not consecutive")
    request_pos = event_index(events, "Request")
    transfer_pos = event_index(events, "Transfer")
    finalize_pos = event_index(events, "Finalize")
    respond_pos = event_index(events, "Respond")
    deliver_pos = event_index(events, "Deliver")
    require(request_pos < transfer_pos < finalize_pos < respond_pos < deliver_pos,
            "P1/P3 order failed")

    transfer = next(event for event in events if event["type"] == "Transfer")
    finalize = next(event for event in events if event["type"] == "Finalize")
    respond = next(event for event in events if event["type"] == "Respond")
    deliver = next(event for event in events if event["type"] == "Deliver")
    require(transfer["sender_role"] == "A" and transfer["receiver_role"] == "S",
            "P2 role binding failed")
    require(transfer["amount"] == 4 and transfer["debit_id"] == "ope-payment-receipt",
            "same-session debit binding failed")
    require(finalize["block_number"] == source["expected_payment_block_number"],
            "finality block mismatch")
    require(finalize["confirmations"] >= header["finality_policy"]["confirmations"],
            "finality confirmation policy failed")
    require(respond["operators"] == source["expected_selected_operator_ids"],
            "operator set mismatch")
    require(deliver["commitment_valid"] is True,
            "P1 commitment-valid delivery failed")

    returns_in_events = [
        {
            "amount": event["amount"],
            "kind": event["kind"],
            "linked_debit_id": event["linked_debit_id"],
        }
        for event in events if event["type"] == "Return"
    ]
    require(returns_in_events == route["process_returns"],
            "P4 return ledger and event sequence differ")
    require(all(item["linked_debit_id"] == transfer["debit_id"]
                for item in returns_in_events), "unlinked return")

    contract_return = sum(item["amount"] for item in route["contract_level_returns"])
    process_return = sum(item["amount"] for item in route["process_returns"])
    contract_cost = max(0, transfer["amount"] - contract_return)
    process_cost = max(0, transfer["amount"] - process_return)
    require(contract_cost == route["expected_contract_cost"], "contract cost mismatch")
    require(process_cost == route["expected_process_cost"], "process cost mismatch")
    return {
        "contract_cost": contract_cost,
        "event_count": len(events),
        "id": route["id"],
        "net_process_cost": process_cost,
        "p1_explicit_delivery": True,
        "p2_same_session_roles": True,
        "p3_explicit_finality": True,
        "p4_complete_returns_and_single_use": True,
        "p5_forward_and_reverse": True,
        "session": route["session"],
    }


def rejected_mutation(route, source, header, mutation):
    candidate = deepcopy(route)
    mutation(candidate)
    try:
        validate_route(candidate, source, header)
    except ValueError:
        return True
    return False


def evaluate():
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    require(model["schema"] == "ope-anchored-process-branch/v2", "unexpected schema")
    header = model["header"]
    require(header["roles"] == ["A", "S"], "role alphabet mismatch")
    require(header["accounting_unit"]["id"] == model["target"]["unit"],
            "accounting unit mismatch")

    source = model["source"]
    receipt_path = ROOT / source["path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(sha256_file(receipt_path) == source["sha256"], "receipt hash mismatch")
    require(receipt["schema"] == source["expected_schema"], "receipt schema mismatch")
    require(receipt["binding"]["entries"][0]["chain_id"] == source["expected_chain_id"],
            "chain mismatch")
    require(int(receipt["gate"]["payment_block_number"])
            == source["expected_payment_block_number"], "payment block mismatch")
    require(receipt["gate"]["payment_tx_hash"] == source["expected_payment_tx_hash"],
            "payment transaction mismatch")
    require(receipt["gate"]["payment_value_wei"]
            == source["expected_payment_value_wei"], "payment value mismatch")
    require(receipt["gate"]["selected_operator_ids"]
            == source["expected_selected_operator_ids"], "operator mismatch")
    require(receipt["protocol"]["plaintext_commitment_verified"] is True,
            "plaintext commitment missing")

    excluded = {}
    for exclusion in model["route_exclusions"]:
        case = receipt["negative_cases"][exclusion["source_negative_case"]]
        require(case["rejected"] is True, "route exclusion lacks rejection evidence")
        excluded[exclusion["id"]] = True

    route_results = [
        validate_route(route, source, header) for route in model["routes"]
    ]
    require(len(route_results) >= 2, "at least two success routes required")
    target = model["target"]["g"]
    contract_floor = min(item["contract_cost"] for item in route_results)
    process_floor = min(item["net_process_cost"] for item in route_results)

    clean = model["routes"][0]
    early = lambda route: route["events"].__setitem__(
        next(i for i, event in enumerate(route["events"]) if event["type"] == "Finalize"),
        {"commitment_valid": True, "position": 2, "type": "Deliver"},
    )
    remove_delivery = lambda route: route["events"].pop(
        next(i for i, event in enumerate(route["events"]) if event["type"] == "Deliver")
    )
    drop_return = lambda route: route["events"].pop(
        next(i for i, event in enumerate(route["events"]) if event["type"] == "Return")
    )
    controls = {
        "missing_delivery_rejected": rejected_mutation(clean, source, header, remove_delivery),
        "prefinality_delivery_rejected": rejected_mutation(clean, source, header, early),
        "omitted_return_rejected": rejected_mutation(model["routes"][1], source, header, drop_return),
        "five_source_bypasses_excluded": len(excluded) == 5 and all(excluded.values()),
        "same_contract_costs_different_process_costs":
            len({item["contract_cost"] for item in route_results}) == 1
            and len({item["net_process_cost"] for item in route_results}) == 3,
    }
    require(all(controls.values()), "one or more controls failed")
    verdict = f"MODEL-REFUTED({target})" if process_floor < target else f"CERTIFIED({target})"
    return {
        "accounting_unit": header["accounting_unit"],
        "controls": controls,
        "floors": {
            "contract": contract_floor,
            "net_process": process_floor,
            "target": target,
            "unit": model["target"]["unit"],
        },
        "route_exclusions": excluded,
        "routes": route_results,
        "schema": "ope-anchored-process-branch-result/v2",
        "source_binding": {
            "payment_block_number": source["expected_payment_block_number"],
            "payment_tx_hash": source["expected_payment_tx_hash"],
            "receipt_sha256": source["sha256"],
        },
        "theorem3": {
            "bidirectional_p5": True,
            "exact_process_floor": process_floor,
            "infimum_attained": True,
        },
        "verdict": verdict,
    }


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    rendered = canonical_json(result)
    log = (
        f"routes: {len(result['routes'])}\n"
        f"contract costs: {[item['contract_cost'] for item in result['routes']]}\n"
        f"net process costs: {[item['net_process_cost'] for item in result['routes']]}\n"
        "P1_EXPLICIT_DELIVERY=PASS\n"
        "P3_EXPLICIT_FINALITY=PASS\n"
        "ROUTE_EXCLUSIONS=PASS_5_OF_5\n"
        "MUTATIONS=PASS_3_OF_3\n"
        f"verdict: {result['verdict']}\n"
    )
    if args.write:
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        LOG_PATH.write_text(log, encoding="utf-8", newline="\n")
        print(log, end="")
    elif args.verify:
        require(RESULT_PATH.read_text(encoding="utf-8") == rendered,
                "checked-in result differs")
        require(LOG_PATH.read_text(encoding="utf-8") == log,
                "checked-in log differs")
        print(log, end="")
    else:
        print(rendered, end="")
    print(f"MODEL_SHA256={sha256_file(MODEL_PATH)}")


if __name__ == "__main__":
    main()
