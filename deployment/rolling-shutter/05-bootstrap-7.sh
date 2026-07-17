#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x

"${DC[@]}" run --rm --no-deps --entrypoint /rolling-shutter chain-0-validator \
  op-bootstrap fetch-keyperset --config /config/op-bootstrap.toml
"${DC[@]}" run --rm --no-deps --entrypoint /rolling-shutter chain-0-validator \
  op-bootstrap --config /config/op-bootstrap.toml

for attempt in {1..180}; do
  ready="$("${DC[@]}" exec -T db psql -U postgres -d keyper-0 -tAc \
    'select count(*) from dkg_result where success = true;' | tr -d '[:space:]')"
  if [[ "${ready:-0}" -ge 1 ]]; then
    echo "successful DKG observed after $attempt seconds"
    exit 0
  fi
  sleep 1
done
echo "timed out waiting for successful DKG" >&2
exit 1
