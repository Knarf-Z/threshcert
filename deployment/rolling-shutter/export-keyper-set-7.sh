#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x

OUTPUT="${KEYPER_SET_OUTPUT:-$FC_ROOT/../runtime/keyper-set.json}"
index="$("${DC[@]}" exec -T db psql -U postgres -d keyper-0 -tAc \
  'select max(keyper_config_index) from eons;' | tr -d '[:space:]')"
"$FC_ROOT/build-exporter.sh"
mkdir -p "$(dirname "$OUTPUT")"
"$FC_ROOT/bin/fc-evidence-exporter" \
  --database-url 'postgres://postgres@127.0.0.1:15432/keyper-0?sslmode=disable' \
  --keyper-config-index "$index" --keyper-set-only --output "$OUTPUT"
echo "keyper set written to $OUTPUT"
