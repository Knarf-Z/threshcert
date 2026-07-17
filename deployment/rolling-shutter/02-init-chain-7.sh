#!/usr/bin/env bash
source "$(dirname "$0")/common-7.sh"
set -x

"${DC[@]}" stop blockchain chain-{0..6}-validator chain-seed || true
"${DC[@]}" rm -f blockchain chain-{0..6}-validator chain-seed || true
"${BB[@]}" rm -rf /data/chain-{0..6}-validator /data/chain-seed /data/deployments
"${BB[@]}" mkdir -p /data/chain-{0..6}-validator/config /data/chain-seed/config
"${BB[@]}" chmod -R a+rwX /data/chain-{0..6}-validator/config /data/chain-seed/config

"${DC[@]}" up -d blockchain
sleep 5
"${DC[@]}" run --rm deploy-contracts
"$THRESHCERT_ROOT/get-contracts-7.sh"

"${DC[@]}" run --rm --no-deps chain-seed init --root /chain --blocktime 1 \
  --listen-address "tcp://0.0.0.0:$TM_RPC_PORT" --role seed
seed_node="$(cat "$SETUP/data/chain-seed/config/node_key.json.id")@chain-seed:$TM_P2P_PORT"
"${BB[@]}" sed -i '/^moniker/c\moniker = "chain-seed"' /data/chain-seed/config/config.toml

for index in {0..6}; do
  service="chain-$index-validator"
  "${DC[@]}" run --rm --no-deps "$service" init --root /chain \
    --genesis-keyper 0x440Dc6F164e9241F04d282215ceF2780cd0B755e \
    --blocktime 1 --listen-address "tcp://0.0.0.0:$TM_RPC_PORT" --role validator
  config="/data/$service/config/config.toml"
  "${BB[@]}" sed -i "/ValidatorPublicKey/cValidatorPublicKey = \"$(cat "$SETUP/data/$service/config/priv_validator_pubkey.hex")\"" "/config/keyper-$index.toml"
  "${BB[@]}" sed -i "/^seeds =/cseeds = \"$seed_node\"" "$config"
  "${BB[@]}" sed -i "/^external_address =/cexternal_address = \"$service:$TM_P2P_PORT\"" "$config"
  "${BB[@]}" sed -i "/^moniker/cmoniker = \"$service\"" "$config"
done
for destination in "$SETUP/data/chain-seed/config" "$SETUP"/data/chain-{1..6}-validator/config; do
  cp "$SETUP/data/chain-0-validator/config/genesis.json" "$destination/genesis.json"
done
"${DC[@]}" stop -t 30
