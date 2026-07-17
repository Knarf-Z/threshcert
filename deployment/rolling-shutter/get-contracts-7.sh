#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x

run_json="$SETUP/data/deployments/Deploy.service.s.sol/31337/run-latest.json"

for name in KeyperSetManager KeyperSet KeyBroadcastContract ShutterRegistry; do
  value="$(
    python3 - "$run_json" "$name" <<'PY'
import json
import sys

run_json = sys.argv[1]
contract_name = sys.argv[2]

with open(run_json, "r", encoding="utf-8") as handle:
    data = json.load(handle)

addresses = [
    tx.get("contractAddress", "")
    for tx in data.get("transactions", [])
    if tx.get("function") is None
    and tx.get("contractName") == contract_name
    and tx.get("contractAddress")
]

print(addresses[-1] if addresses else "")
PY
  )"

  [[ "$value" != "null" && -n "$value" ]] || {
    echo "missing deployed $name" >&2
    exit 1
  }

  for index in {0..6}; do
    "${BB[@]}" sed -i \
      "/^$name =/c$name = \"$value\"" \
      "/config/keyper-$index.toml"
  done

  if [[ "$name" == "KeyperSetManager" ]]; then
    "${BB[@]}" sed -i \
      "/^KeyperSetManager =/cKeyperSetManager = \"$value\"" \
      /config/bootstrap.toml

    "${BB[@]}" sed -i \
      "/^KeyperSetManager =/cKeyperSetManager = \"$value\"" \
      /config/op-bootstrap.toml
  fi
done