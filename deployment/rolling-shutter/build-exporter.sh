#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM="${ROLLING_SHUTTER_DIR:-$ROOT/upstream}"
EXPECTED_COMMIT="d143fffcf51f85b30375134d2d29756417f333b9"

if [[ ! -f "$UPSTREAM/rolling-shutter/go.mod" ]]; then
  echo "missing pinned Rolling Shutter checkout at $UPSTREAM" >&2
  echo "run ./prepare-upstream.sh first" >&2
  exit 1
fi

actual="$(git -C "$UPSTREAM" rev-parse HEAD)"
if [[ "$actual" != "$EXPECTED_COMMIT" ]]; then
  echo "unexpected Rolling Shutter commit: $actual" >&2
  exit 1
fi

target="$UPSTREAM/rolling-shutter/tools/threshcert-evidence-exporter"
mkdir -p "$target" "$ROOT/bin"
cp "$ROOT/evidence-exporter/"*.go "$target/"

docker run --rm \
  --mount "type=bind,src=$UPSTREAM/rolling-shutter,dst=/src" \
  --mount "type=bind,src=$ROOT/bin,dst=/out" \
  --mount "type=volume,src=threshcert-go-mod-cache,dst=/go/pkg/mod" \
  --mount "type=volume,src=threshcert-go-build-cache,dst=/root/.cache/go-build" \
  --workdir /src \
  golang:1.23.8 \
  sh -c '
    set -eu
    go test ./tools/threshcert-evidence-exporter
    go build -trimpath \
      -o /out/threshcert-evidence-exporter \
      ./tools/threshcert-evidence-exporter
  '

chmod +x "$ROOT/bin/threshcert-evidence-exporter" 2>/dev/null || true
echo "built $ROOT/bin/threshcert-evidence-exporter using Docker"