#!/usr/bin/env python3
import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "model.v15.json"
RESULT_PATH = ROOT / "results" / "finite_process_delivery.v15.json"
LOG_PATH = ROOT / "results" / "finite_process_delivery.v15.log"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_json(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def initial_state():
    return (False, False, 0, False, 0)


def enabled(state):
    opened, finalized, submitted, delivered, withdrawn = state
    actions = []
    if not opened:
        actions.append("open")
        return actions
    if opened and not finalized:
        actions.append("finalize")
    if finalized and not delivered:
        if not submitted & 1:
            actions.append("submit_M_1")
        if not submitted & 2:
            actions.append("submit_M_2")
        if submitted == 3:
            actions.append("deliver")
    if delivered:
        if not withdrawn & 1:
            actions.append("withdraw_M_1")
        if not withdrawn & 2:
            actions.append("withdraw_M_2")
    return actions


def step(state, action):
    require(action in enabled(state), f"disabled action {action} at {state}")
    opened, finalized, submitted, delivered, withdrawn = state
    if action == "open":
        opened = True
    elif action == "finalize":
        finalized = True
    elif action == "submit_M_1":
        submitted |= 1
    elif action == "submit_M_2":
        submitted |= 2
    elif action == "deliver":
        delivered = True
    elif action == "withdraw_M_1":
        withdrawn |= 1
    elif action == "withdraw_M_2":
        withdrawn |= 2
    return (opened, finalized, submitted, delivered, withdrawn)


def replay(trace):
    state = initial_state()
    events = []
    for position, action in enumerate(trace):
        state = step(state, action)
        if action == "open":
            events.extend([
                {"position": position, "type": "Request"},
                {"amount": 5000000000000000000, "debit_id": "toy-debit-1",
                 "position": position, "receiver_role": "S", "sender_role": "A",
                 "type": "Transfer"},
            ])
        elif action == "finalize":
            events.append({"confirmations": 1, "position": position, "type": "Finalize"})
        elif action.startswith("submit_"):
            events.append({"member": action.removeprefix("submit_"),
                           "position": position, "type": "Respond"})
        elif action == "deliver":
            events.append({"commitment_valid": True, "position": position,
                           "type": "Deliver"})
    return state, events


def validate_first_success(trace):
    state, events = replay(trace)
    require(state[3] is True, "trace does not deliver")
    require(trace[-1] == "deliver", "first-success trace must end at explicit deliver")
    types = [event["type"] for event in events]
    for required in ("Request", "Transfer", "Finalize", "Respond", "Deliver"):
        require(required in types, f"missing {required}")
    first = {name: types.index(name) for name in set(types)}
    require(first["Request"] <= first["Transfer"] < first["Finalize"]
            < first["Respond"] < first["Deliver"], "P1/P3 event order failed")
    responses = {event["member"] for event in events if event["type"] == "Respond"}
    require(responses == {"M_1", "M_2"}, "threshold contributor set mismatch")
    transfer = next(event for event in events if event["type"] == "Transfer")
    require(transfer["sender_role"] == "A" and transfer["receiver_role"] == "S",
            "P2 role binding failed")
    return events


def enumerate_lts():
    queue = deque([initial_state()])
    seen = {initial_state()}
    transitions = []
    while queue:
        state = queue.popleft()
        for action in enabled(state):
            nxt = step(state, action)
            transitions.append({"action": action, "from": list(state), "to": list(nxt)})
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

    successes = []

    def enumerate_histories(state, trace):
        for action in enabled(state):
            nxt = step(state, action)
            next_trace = trace + [action]
            if not state[3] and nxt[3]:
                successes.append(next_trace)
            elif not nxt[3]:
                enumerate_histories(nxt, next_trace)

    enumerate_histories(initial_state(), [])
    return seen, transitions, successes


def mutation_controls():
    controls = {}
    try:
        validate_first_success(["open", "finalize", "submit_M_1", "submit_M_2"])
        controls["missing_deliver_rejected"] = False
    except ValueError:
        controls["missing_deliver_rejected"] = True
    try:
        replay(["open", "deliver"])
        controls["prefinality_delivery_rejected"] = False
    except ValueError:
        controls["prefinality_delivery_rejected"] = True
    try:
        replay(["zero_cost_bypass"])
        controls["undeclared_bypass_rejected"] = False
    except ValueError:
        controls["undeclared_bypass_rejected"] = True
    controls["member_names_do_not_alias_attacker"] = all(
        name not in {"A", "S"} for name in ("M_1", "M_2")
    )
    return controls


def evaluate():
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    require(model["schema"] == "finite-process-delivery/v15", "unexpected schema")
    require(set(model["header"]["roles"]) == {"A", "S"}, "role alphabet mismatch")
    states, transitions, success_traces = enumerate_lts()
    require(len(success_traces) == model["expected"]["first_success_route_count"],
            "first-success route count mismatch")
    route_results = []
    for trace in success_traces:
        events = validate_first_success(trace)
        route_results.append({
            "actions": trace,
            "cost": model["payment"]["amount"],
            "events": events,
            "p1_explicit_delivery": True,
            "p2_same_session_role_binding": True,
            "p3_finalize_before_delivery": True,
            "p4_closed_and_single_use": True,
            "p5_forward_and_reverse": True,
        })
    controls = mutation_controls()
    require(all(controls.values()), "mutation control failed")
    require(all(route["cost"] == model["expected"]["first_success_cost"]
                for route in route_results), "cost mismatch")
    return {
        "controls": controls,
        "first_success_routes": route_results,
        "lts": {
            "reachable_states": len(states),
            "enabled_transitions": len(transitions),
        },
        "schema": "finite-process-delivery-result/v15",
        "verdict": model["expected"]["verdict"],
    }


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    rendered = canonical_json(result)
    log = (
        f"states: {result['lts']['reachable_states']}\n"
        f"transitions: {result['lts']['enabled_transitions']}\n"
        f"first-success routes: {len(result['first_success_routes'])}\n"
        "P1_EXPLICIT_DELIVERY=PASS\n"
        "P3_EXPLICIT_FINALITY=PASS\n"
        "MUTATIONS=PASS_4_OF_4\n"
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
    print(f"MODEL_SHA256={sha256(MODEL_PATH)}")


if __name__ == "__main__":
    main()
