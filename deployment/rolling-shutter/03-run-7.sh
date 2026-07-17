#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x
"${DC[@]}" up -d db blockchain chain-seed chain-{0..6}-validator bootnode-0 keyper-{0..6}
