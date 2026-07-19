#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x

"${DC[@]}" build rs-build blockchain deploy-contracts

docker run --rm -v "$SETUP/config:/config" rolling-shutter \
  p2pnode generate-config --output /config/bootstrap.toml --force
for index in {0..6}; do
  docker run --rm -v "$SETUP/config:/config" rolling-shutter \
    shutterservicekeyper generate-config --output "/config/keyper-$index.toml" --force
done
python3 "$FC_ROOT/configure-runtime.py" "$SETUP/config"
