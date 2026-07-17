#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


def replace_scalar(text: str, key: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(key)}\s*=.*$"
    changed, count = re.subn(pattern, f"{key} = {value}", text)
    if count != 1:
        raise SystemExit(f"expected one {key} field, found {count}")
    return changed


def replace_array(text: str, key: str, values: list[str]) -> str:
    pattern = rf"(?ms)^{re.escape(key)}\s*=\s*(?:\[[^\n]*\]|\[.*?^\])"
    body = "\n".join(f'    "{value}",' for value in values)
    changed, count = re.subn(pattern, f"{key} = [\n{body}\n]", text)
    if count != 1:
        raise SystemExit(f"expected one {key} array, found {count}")
    return changed


def header_value(text: str, label: str) -> str:
    match = re.search(rf"(?m)^# {re.escape(label)}:\s*(\S+)\s*$", text)
    if not match:
        raise SystemExit(f"missing generated {label} header")
    return match.group(1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: configure-runtime.py SETUP_CONFIG_DIR")
    config = Path(sys.argv[1]).resolve()
    bootstrap_path = config / "bootstrap.toml"
    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    bootstrap_peer = header_value(bootstrap, "Peer identity")
    bootstrap = replace_scalar(bootstrap, "ListenMessages", "true")
    bootstrap = replace_scalar(bootstrap, "ListenAddresses", '["/ip4/0.0.0.0/tcp/23000"]')
    bootstrap = replace_array(
        bootstrap,
        "CustomBootstrapAddresses",
        [f"/dns4/bootnode-0/tcp/23000{bootstrap_peer}"],
    )
    bootstrap = replace_scalar(bootstrap, "DiscoveryNamespace", '"threshcert-shutter-4of7"')
    bootstrap_path.write_text(bootstrap, encoding="utf-8")

    addresses: list[str] = []
    for index in range(7):
        path = config / f"keyper-{index}.toml"
        text = path.read_text(encoding="utf-8")
        addresses.append(header_value(text, "Ethereum address"))
        text = replace_scalar(text, "InstanceID", "0")
        text = replace_scalar(text, "DatabaseURL", f'"postgres://postgres@db:5432/keyper-{index}"')
        text = replace_scalar(text, "HTTPEnabled", "false")
        text = replace_scalar(text, "ListenAddresses", '["/ip4/0.0.0.0/tcp/23000"]')
        text = replace_array(
            text,
            "CustomBootstrapAddresses",
            [f"/dns4/bootnode-0/tcp/23000{bootstrap_peer}"],
        )
        text = replace_scalar(text, "DiscoveryNamespace", '"threshcert-shutter-4of7"')
        text = replace_scalar(text, "SyncStartBlockNumber", "0")
        text = replace_scalar(text, "SyncMonitorCheckInterval", "60")
        text = replace_scalar(text, "DeploymentDir", '"/deployments/localhost/"')
        text = replace_scalar(text, "EthereumURL", '"ws://blockchain:8545/"')
        text = replace_scalar(text, "ShuttermintURL", f'"http://chain-{index}-validator:26657"')
        text = replace_scalar(text, "DKGPhaseLength", "8")
        text = replace_scalar(text, "DKGStartBlockDelta", "5")
        path.write_text(text, encoding="utf-8")

    node_deploy = {"keypers": [addresses]}
    (config / "node-deploy.json").write_text(
        json.dumps(node_deploy, indent=2) + "\n", encoding="utf-8"
    )
    print("generated fresh 7-Keyper runtime configuration")
    for index, address in enumerate(addresses):
        print(f"keyper[{index}]={address}")


if __name__ == "__main__":
    main()
