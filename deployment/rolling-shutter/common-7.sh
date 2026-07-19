#!/usr/bin/env bash
set -euo pipefail

FC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM="${ROLLING_SHUTTER_DIR:-$FC_ROOT/upstream}"
SETUP="$UPSTREAM/docker-test-setup-api"
COMPOSE_EXTRA="$FC_ROOT/docker-compose.7.yml"
EXPECTED_COMMIT="d143fffcf51f85b30375134d2d29756417f333b9"
DEPLOY_KEY="${DEPLOY_KEY:-0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80}"
export DEPLOY_KEY

[[ -f "$SETUP/docker-compose.yml" ]] || { echo "run prepare-upstream.sh first" >&2; exit 1; }
actual="$(git -C "$UPSTREAM" rev-parse HEAD)"
[[ "$actual" == "$EXPECTED_COMMIT" ]] || { echo "unexpected upstream commit $actual" >&2; exit 1; }

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose --project-directory "$SETUP" -f "$SETUP/docker-compose.yml" -f "$COMPOSE_EXTRA")
else
  DC=(docker compose --project-directory "$SETUP" -f "$SETUP/docker-compose.yml" -f "$COMPOSE_EXTRA")
fi

BB=(docker run --rm -v "$SETUP/data:/data" -v "$SETUP/config:/config" -w / busybox)
TM_P2P_PORT=26656
TM_RPC_PORT=26657
