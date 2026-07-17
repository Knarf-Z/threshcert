#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"

# Register one future Shutter identity without requiring jq.  The default
# trigger is 30 minutes in the future so the matching Chiado release job can
# be opened and checked before any shares are emitted.
run_json="$SETUP/data/deployments/Deploy.service.s.sol/31337/run-latest.json"

export ShutterRegistry="$(python3 - "$run_json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

addresses = [
    tx.get("contractAddress")
    for tx in data.get("transactions", [])
    if tx.get("function") is None
    and tx.get("contractName") == "ShutterRegistry"
    and tx.get("contractAddress")
]
if not addresses:
    raise SystemExit("ShutterRegistry deployment was not found")
print(addresses[-1])
PY
)"

[[ "$ShutterRegistry" =~ ^0x[0-9a-fA-F]{40}$ ]] || {
  echo "invalid ShutterRegistry address" >&2
  exit 1
}

export KEYPER_CONFIG_INDEX="$(
  "${DC[@]}" exec -T db psql -U postgres -d keyper-0 -tAc \
    'select max(keyper_config_index) from eons;' | tr -d '[:space:]'
)"
[[ "$KEYPER_CONFIG_INDEX" =~ ^[0-9]+$ ]] || {
  echo "no active Keyper configuration" >&2
  exit 1
}

export EON="$KEYPER_CONFIG_INDEX"
identity_delay="${IDENTITY_DELAY_SECONDS:-1800}"
[[ "$identity_delay" =~ ^[0-9]+$ ]] && (( identity_delay >= 300 )) || {
  echo "IDENTITY_DELAY_SECONDS must be an integer of at least 300" >&2
  exit 1
}

now="$(date +%s)"
export TIMESTAMP="${TIMESTAMP:-$((now + identity_delay))}"
[[ "$TIMESTAMP" =~ ^[0-9]+$ ]] && (( TIMESTAMP > now + 120 )) || {
  echo "TIMESTAMP must be at least 120 seconds in the future" >&2
  exit 1
}

export IDENTITY_PREFIX="${IDENTITY_PREFIX:-0x$(openssl rand -hex 32)}"
[[ "$IDENTITY_PREFIX" =~ ^0x[0-9a-fA-F]{64}$ ]] || {
  echo "IDENTITY_PREFIX must be a 32-byte 0x-prefixed value" >&2
  exit 1
}
export REGISTRY_ADDRESS="$ShutterRegistry"

"${DC[@]}" run --rm --no-deps register-identity

sender="$(
  "${DC[@]}" run --rm --no-deps --entrypoint cast deploy-contracts \
    wallet address --private-key "$DEPLOY_KEY" | tr -d '[:space:]'
)"
[[ "$sender" =~ ^0x[0-9a-fA-F]{40}$ ]] || {
  echo "could not derive the local identity sender" >&2
  exit 1
}

identity_preimage="$(
  "${DC[@]}" run --rm --no-deps --entrypoint cast deploy-contracts \
    keccak "${IDENTITY_PREFIX}${sender#0x}" | tr -d '[:space:]'
)"
identity_hash="$(
  "${DC[@]}" run --rm --no-deps --entrypoint cast deploy-contracts \
    keccak "$identity_preimage" | tr -d '[:space:]'
)"

[[ "$identity_preimage" =~ ^0x[0-9a-fA-F]{64}$ ]] || {
  echo "invalid identity preimage" >&2
  exit 1
}
[[ "$identity_hash" =~ ^0x[0-9a-fA-F]{64}$ ]] || {
  echo "invalid identity hash" >&2
  exit 1
}

identity_output="$THRESHCERT_ROOT/../runtime/identity.json"
mkdir -p "$(dirname "$identity_output")"
python3 - \
  "$identity_output" \
  "$KEYPER_CONFIG_INDEX" \
  "$IDENTITY_PREFIX" \
  "$sender" \
  "$identity_preimage" \
  "$identity_hash" \
  "$TIMESTAMP" <<'PY'
import datetime
import json
import sys

(
    output,
    keyper_config_index,
    identity_prefix,
    sender,
    identity_preimage,
    identity_hash,
    trigger_timestamp,
) = sys.argv[1:]

record = {
    "schema": "threshcert-shutter-identity-v1",
    "generatedAt": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    "keyperConfigIndex": keyper_config_index,
    "identityPrefix": identity_prefix,
    "sender": sender,
    "identityPreimage": identity_preimage,
    "identityHash": identity_hash,
    "triggerTimestamp": trigger_timestamp,
}
with open(output, "w", encoding="utf-8", newline="\n") as handle:
    json.dump(record, handle, indent=2)
    handle.write("\n")
PY

echo "identity_record=$identity_output"
echo "keyper_config_index=$KEYPER_CONFIG_INDEX"
echo "identity_preimage=$identity_preimage"
echo "identity_hash=$identity_hash"
echo "trigger_timestamp=$TIMESTAMP"
echo "identity_registration=PASS"
echo "Open the matching Chiado release job before the trigger timestamp."
