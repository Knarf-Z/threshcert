import { resolve } from "node:path";

import { network } from "hardhat";
import { getAddress, isAddress, parseEther, type Address } from "viem";

import { readJson, writeJson } from "../src/io.js";
import { transactionRecord } from "../src/records.js";
import type { KeyperEntry, KeyperSetFile, RewardedDeploymentFile } from "../src/schema.js";

/// Deploys the parallel, additive `BondedKeyperSlasherRewarded` contract --
/// the un-rewarded `BondedKeyperSlasher` and its own `deploy.ts` are
/// untouched, since `BondedKeyperSlasher.sol`'s exact source hash is bound
/// into the already-recorded `certificates/chiado-execution-certificate.json`
/// from a real prior on-chain run. This script and its contract are new,
/// not a replacement.

function envAddress(name: string, fallback?: Address): Address {
  const raw = process.env[name]?.trim();
  if (!raw) {
    if (fallback !== undefined) return fallback;
    throw new Error(`missing required environment variable ${name}`);
  }
  if (!isAddress(raw)) throw new Error(`${name} is not an Ethereum address`);
  return getAddress(raw);
}

async function externalKeypers(): Promise<KeyperEntry[]> {
  const path = process.env.KEYPER_SET_FILE?.trim();
  if (!path) throw new Error("Chiado deployment requires KEYPER_SET_FILE");
  const set = await readJson<KeyperSetFile>(path);
  if (set.schema !== "fc-keyper-set-v1") throw new Error("unknown keyper-set schema");
  if (set.threshold !== 4 || set.keypers.length !== 7) {
    throw new Error("keyper set must be exactly 4-of-7");
  }
  const sorted = [...set.keypers].sort((a, b) => a.index - b.index);
  const uniqueAddresses = new Set(sorted.map((keyper) => keyper.address.toLowerCase()));
  if (uniqueAddresses.size !== 7) throw new Error("keyper addresses must be unique");
  sorted.forEach((keyper, expected) => {
    if (keyper.index !== expected || !isAddress(keyper.address)) {
      throw new Error("keyper indices must be contiguous from 0 through 6");
    }
  });
  return sorted.map((keyper) => ({
    index: keyper.index,
    address: getAddress(keyper.address),
  }));
}

const connection = await network.create();
const { viem, networkName } = connection;
const publicClient = await viem.getPublicClient();
const wallets = await viem.getWalletClients();
if (wallets.length === 0) throw new Error("network exposes no deployment wallet");

const ownerWallet = wallets[0];
const chainId = await publicClient.getChainId();
const local = chainId === 31337;
const verifier = envAddress(
  "EVIDENCE_VERIFIER_ADDRESS",
  local ? wallets[1]?.account.address : undefined,
);
const treasury = envAddress(
  "PENALTY_TREASURY_ADDRESS",
  local ? wallets[2]?.account.address : ownerWallet.account.address,
);
const keypers = local
  ? wallets.slice(3, 10).map((wallet, index) => ({
      index,
      address: getAddress(wallet.account.address),
    }))
  : await externalKeypers();
if (keypers.length !== 7) throw new Error("seven Keyper addresses are required");

// Sized against the worst-case observed slashEarlyShare gas cost on Chiado
// (108,629 gas @ 10,000,000,007 wei/gas ~= 1.0863e15 wei; see
// results/slashing-chiado.json and scripts/report_slashing_fee_ratio.py),
// with roughly a 9x safety margin against gas-price movement -- not an
// arbitrary nominal figure.
const callerReward = process.env.CALLER_REWARD_WEI
  ? BigInt(process.env.CALLER_REWARD_WEI)
  : local
    ? parseEther("0.1")
    : 10_000_000_000_000_000n; // 1e16 wei
if (callerReward <= 0n) throw new Error("CALLER_REWARD_WEI must be positive");

const bond = process.env.BOND_WEI_REWARDED
  ? BigInt(process.env.BOND_WEI_REWARDED)
  : local
    ? parseEther("2")
    : 20_000_000_000_000_000n; // 2e16 wei
if (bond <= callerReward) throw new Error("BOND_WEI_REWARDED must exceed CALLER_REWARD_WEI");

const { contract, deploymentTransaction } = await viem.sendDeploymentTransaction(
  "BondedKeyperSlasherRewarded",
  [ownerWallet.account.address, verifier, treasury, callerReward],
  { client: { wallet: ownerWallet, public: publicClient } },
);
const deployReceipt = await publicClient.waitForTransactionReceipt({
  hash: deploymentTransaction.hash,
});

const registrations: RewardedDeploymentFile["transactions"]["registrations"] = [];
for (const keyper of keypers) {
  const hash = await contract.write.registerMember(
    [keyper.index, keyper.address],
    { account: ownerWallet.account, value: bond },
  );
  const receipt = await publicClient.waitForTransactionReceipt({ hash });
  registrations.push({ memberIndex: keyper.index, ...transactionRecord(receipt) });
}
const freezeHash = await contract.write.freezeCommittee({ account: ownerWallet.account });
const freezeReceipt = await publicClient.waitForTransactionReceipt({ hash: freezeHash });

const result: RewardedDeploymentFile = {
  schema: "fc-bonded-keyper-deployment-rewarded-v1",
  generatedAt: new Date().toISOString(),
  networkName,
  chainId,
  contract: contract.address,
  owner: getAddress(ownerWallet.account.address),
  verifier,
  treasury,
  committeeSize: 7,
  threshold: 4,
  bondWeiPerMember: bond.toString(),
  callerRewardWei: callerReward.toString(),
  totalBondWei: (await contract.read.totalBond()).toString(),
  initialCertificateWei: (await contract.read.currentCertificate()).toString(),
  keypers,
  transactions: {
    deploy: transactionRecord(deployReceipt),
    registrations,
    freeze: transactionRecord(freezeReceipt),
  },
};

const output = process.env.DEPLOYMENT_OUTPUT?.trim()
  ?? `results/deployment-${networkName}-rewarded.json`;
console.log(`contract=${contract.address}`);
console.log(`certificate_wei=${result.initialCertificateWei}`);
console.log(`caller_reward_wei=${result.callerRewardWei}`);
console.log(`deployment_record=${await writeJson(resolve(output), result)}`);
