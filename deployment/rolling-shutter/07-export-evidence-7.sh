#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"

# Export and independently validate all seven shares without requiring jq.
IDENTITY_FILE="${IDENTITY_FILE:-$FC_ROOT/../runtime/identity.json}"
OUTPUT="${EVIDENCE_OUTPUT:-$FC_ROOT/../evidence/shutter-evidence.json}"

[[ -f "$IDENTITY_FILE" ]] || {
  echo "identity record not found: $IDENTITY_FILE" >&2
  exit 1
}

identity_values="$(python3 - "$IDENTITY_FILE" <<'PY'
import json
import re
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
if data.get("schema") != "fc-shutter-identity-v1":
    raise SystemExit("unknown identity schema")
index = str(data.get("keyperConfigIndex", ""))
preimage = str(data.get("identityPreimage", ""))
if not re.fullmatch(r"[0-9]+", index):
    raise SystemExit("invalid keyperConfigIndex")
if not re.fullmatch(r"0x[0-9a-fA-F]{64}", preimage):
    raise SystemExit("invalid identityPreimage")
print(index)
print(preimage)
PY
)"

index="$(printf '%s\n' "$identity_values" | sed -n '1p')"
preimage="$(printf '%s\n' "$identity_values" | sed -n '2p')"

"$FC_ROOT/build-exporter.sh"
mkdir -p "$(dirname "$OUTPUT")"

attempts="${EVIDENCE_WAIT_ATTEMPTS:-3600}"
[[ "$attempts" =~ ^[0-9]+$ ]] && (( attempts > 0 )) || {
  echo "EVIDENCE_WAIT_ATTEMPTS must be a positive integer" >&2
  exit 1
}

log_file="$(mktemp)"
trap 'rm -f "$log_file"' EXIT

for ((attempt = 1; attempt <= attempts; attempt++)); do
  if "$FC_ROOT/bin/fc-evidence-exporter" \
    --database-url 'postgres://postgres@127.0.0.1:15432/keyper-0?sslmode=disable' \
    --keyper-config-index "$index" \
    --instance-id 0 \
    --identity-preimage "$preimage" \
    --require-all=true \
    --output "$OUTPUT" >"$log_file" 2>&1; then
    cat "$log_file"

    python3 - "$OUTPUT" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

checks = {
    "schema": data.get("schema") == "fc-shutter-evidence-v1",
    "threshold": data.get("threshold") == 4,
    "numKeypers": data.get("numKeypers") == 7,
    "shareCount": len(data.get("shares", [])) == 7,
    "aggregateKeyValid": data.get("aggregateKeyValid") is True,
    "reconstructionMatchesStoredKey":
        data.get("reconstructionMatchesStoredKey") is True,
    "allSharesValid": all(
        share.get("shareValid") is True
        and share.get("nativeSignatureValid") is True
        for share in data.get("shares", [])
    ),
}
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("evidence validation failed: " + ", ".join(failed))

print("evidence_share_count=7")
print("aggregate_key_valid=true")
print("reconstruction_matches_stored_key=true")
print("evidence_validation=PASS")
PY

    echo "evidence_record=$OUTPUT"
    exit 0
  fi

  if (( attempt == 1 || attempt % 30 == 0 )); then
    echo "waiting_for_validated_shares attempt=$attempt/$attempts"
    tail -n 3 "$log_file" || true
  fi
  sleep 1
done

cat "$log_file" >&2
echo "timed out waiting for seven validated Shutter shares" >&2
exit 1
