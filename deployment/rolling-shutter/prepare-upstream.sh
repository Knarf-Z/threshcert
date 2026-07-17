#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM="${ROLLING_SHUTTER_DIR:-$ROOT/upstream}"
TAG="v1.4.4"
COMMIT="d143fffcf51f85b30375134d2d29756417f333b9"

if [[ ! -d "$UPSTREAM/.git" ]]; then
  git clone --branch "$TAG" --depth 1 https://github.com/shutter-network/rolling-shutter.git "$UPSTREAM"
fi
actual="$(git -C "$UPSTREAM" rev-parse HEAD)"
if [[ "$actual" != "$COMMIT" ]]; then
  echo "refusing checkout $actual; expected $COMMIT for $TAG" >&2
  exit 1
fi
echo "verified Rolling Shutter $TAG at $COMMIT"
