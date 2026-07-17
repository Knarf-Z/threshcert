#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x

run_json="$SETUP/data/deployments/Deploy.service.s.sol/31337/run-latest.json"
node_json="$SETUP/config/node-deploy.json"

extract_contract() {
  python3 -c '
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

name = sys.argv[2]
addresses = [
    tx.get("contractAddress", "")
    for tx in data.get("transactions", [])
    if tx.get("function") is None
    and tx.get("contractName") == name
    and tx.get("contractAddress")
]

print(addresses[-1] if addresses else "")
' "$run_json" "$1"
}

export KEYPERSETMANAGER_ADDRESS="$(
  extract_contract "KeyperSetManager"
)"

export KEYBROADCAST_ADDRESS="$(
  extract_contract "KeyBroadcastContract"
)"

export KEYPER_ADDRESSES="$(
  python3 -c '
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

print(",".join(data["keypers"][0]))
' "$node_json"
)"

export THRESHOLD=4
export ACTIVATION_DELTA=10

[[ -n "$KEYPERSETMANAGER_ADDRESS" ]] || {
  echo "missing KeyperSetManager address" >&2
  exit 1
}

[[ -n "$KEYBROADCAST_ADDRESS" ]] || {
  echo "missing KeyBroadcastContract address" >&2
  exit 1
}

[[ "$(awk -F, '{print NF}' <<<"$KEYPER_ADDRESSES")" == "7" ]] || {
  echo "expected seven Keypers" >&2
  exit 1
}

"${DC[@]}" run --rm --no-deps add-keyper-set