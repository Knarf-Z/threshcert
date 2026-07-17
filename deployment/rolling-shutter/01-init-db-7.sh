#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x

"${DC[@]}" stop db || true
"${DC[@]}" rm -f db || true
"${BB[@]}" rm -rf /data/db
"${DC[@]}" up -d db
"${DC[@]}" run --rm --no-deps wait-for-db

for index in {0..6}; do
  "${DC[@]}" exec -T db createdb -U postgres "keyper-$index"
  "${DC[@]}" run -T --rm --no-deps "keyper-$index" initdb \
    --config "/config/keyper-$index.toml"
done
"${DC[@]}" stop db
