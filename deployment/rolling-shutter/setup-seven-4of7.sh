#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

"$ROOT/prepare-upstream.sh"
"$ROOT/00-build-and-configure-7.sh"
"$ROOT/01-init-db-7.sh"
"$ROOT/02-init-chain-7.sh"
"$ROOT/03-run-7.sh"
"$ROOT/04-add-keyper-set-7.sh"
"$ROOT/05-bootstrap-7.sh"
"$ROOT/export-keyper-set-7.sh"
echo "Rolling Shutter seven-process 4-of-7 DKG is ready"
