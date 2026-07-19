import { resolve } from "node:path";

import { concat, getAddress, isAddress, isHex, keccak256, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";

import { requireEnv, writeJson } from "../src/io.js";

const prefix = requireEnv("IDENTITY_PREFIX") as Hex;
if (!isHex(prefix) || prefix.length !== 66) {
  throw new Error("IDENTITY_PREFIX must be a 32-byte 0x-prefixed value");
}

let sender = process.env.IDENTITY_SENDER_ADDRESS?.trim();
if (!sender) {
  const key = requireEnv("DEPLOY_KEY") as Hex;
  if (!/^0x[0-9a-fA-F]{64}$/.test(key)) throw new Error("DEPLOY_KEY is malformed");
  sender = privateKeyToAccount(key).address;
}
if (!isAddress(sender)) throw new Error("identity sender is not an Ethereum address");
const address = getAddress(sender);
const identityPreimage = keccak256(concat([prefix, address]));
const keyperConfigIndex = requireEnv("KEYPER_CONFIG_INDEX");
const timestamp = requireEnv("TIMESTAMP");

const result = {
  schema: "fc-shutter-identity-v1",
  generatedAt: new Date().toISOString(),
  keyperConfigIndex,
  identityPrefix: prefix,
  sender: address,
  identityPreimage,
  identityHash: keccak256(identityPreimage),
  triggerTimestamp: timestamp,
};
const output = process.env.IDENTITY_OUTPUT?.trim() ?? "runtime/identity.json";
console.log(`identity_preimage=${identityPreimage}`);
console.log(`identity_record=${await writeJson(resolve(output), result)}`);
