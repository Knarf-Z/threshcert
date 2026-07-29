import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { network } from "hardhat";
import {
  type Abi,
  type Address,
  type Hex,
} from "viem";

const SETTLEMENT_GUARD = "I_UNDERSTAND_PUBLIC_SETTLEMENT";
const CONFIRMATIONS = Number(process.env.PHASE2_CONFIRMATIONS ?? "2");

type ArtifactFile = { abi: Abi };
type Scenario = {
  mode: string;
  contractAddress: Address;
  constructor: { owner: Address };
  job: { releaseTime: string };
  remainingBondWei: string;
};
type DeploymentResult = {
  schema: string;
  network: { chainId: number };
  scenarios: Scenario[];
};

if (process.env.PHASE2_SETTLE !== SETTLEMENT_GUARD) {
  throw new Error(
    `Refusing public-chain settlement. Set PHASE2_SETTLE=${SETTLEMENT_GUARD} only after all recorded release windows have ended.`,
  );
}
if (!Number.isInteger(CONFIRMATIONS) || CONFIRMATIONS < 1) {
  throw new Error("PHASE2_CONFIRMATIONS must be a positive integer.");
}

const root = resolve(import.meta.dirname, "..");
const deployment = JSON.parse(
  await readFile(resolve(root, "results/phase2_chiado.json"), "utf8"),
) as DeploymentResult;
if (deployment.schema !== "fc-trace-then-slash-phase2-chiado-v2") {
  throw new Error("Unexpected deployment result schema.");
}
if (deployment.network.chainId !== 10200) {
  throw new Error("Settlement result is not for Chiado.");
}

const artifact = JSON.parse(
  await readFile(
    resolve(
      root,
      "artifacts/contracts/TraceThenSlash.sol/TraceThenSlash.json",
    ),
    "utf8",
  ),
) as ArtifactFile;

const connection = await network.connect();
const { viem } = connection;
const publicClient = await viem.getPublicClient();
const wallets = await viem.getWalletClients();
const owner = wallets[0];
if (owner?.account === undefined) {
  throw new Error("Chiado deployer account is unavailable.");
}
if ((await publicClient.getChainId()) !== 10200) {
  throw new Error("Connected network is not Chiado.");
}

const ownerAddress = owner.account.address;
const latestBlock = await publicClient.getBlock();
const preflight = [];
for (const scenario of deployment.scenarios) {
  if (
    scenario.constructor.owner.toLowerCase() !== ownerAddress.toLowerCase()
  ) {
    throw new Error(`${scenario.mode}: connected account is not the owner.`);
  }
  const latestReleaseTime = await publicClient.readContract({
    address: scenario.contractAddress,
    abi: artifact.abi,
    functionName: "latestReleaseTime",
  }) as bigint;
  const committeeRetired = await publicClient.readContract({
    address: scenario.contractAddress,
    abi: artifact.abi,
    functionName: "committeeRetired",
  }) as boolean;
  const remainingBond = await publicClient.readContract({
    address: scenario.contractAddress,
    abi: artifact.abi,
    functionName: "totalBond",
  }) as bigint;

  if (committeeRetired) {
    throw new Error(`${scenario.mode}: committee is already retired.`);
  }
  if (remainingBond !== BigInt(scenario.remainingBondWei)) {
    throw new Error(`${scenario.mode}: remaining bond differs from the run.`);
  }
  if (latestBlock.timestamp < latestReleaseTime) {
    throw new Error(
      `${scenario.mode}: release window remains active until ${new Date(
        Number(latestReleaseTime) * 1000,
      ).toISOString()}.`,
    );
  }
  preflight.push({ scenario, latestReleaseTime, remainingBond });
}

const settlements = [];
for (const item of preflight) {
  const hash = await owner.writeContract({
    account: owner.account,
    address: item.scenario.contractAddress,
    abi: artifact.abi,
    functionName: "withdrawRemainingBonds",
    args: [ownerAddress],
  });
  const receipt = await publicClient.waitForTransactionReceipt({
    hash,
    confirmations: CONFIRMATIONS,
  });
  if (receipt.status !== "success") {
    throw new Error(`${item.scenario.mode}: settlement reverted: ${hash}`);
  }
  const remainingAfter = await publicClient.readContract({
    address: item.scenario.contractAddress,
    abi: artifact.abi,
    functionName: "totalBond",
  }) as bigint;
  const retiredAfter = await publicClient.readContract({
    address: item.scenario.contractAddress,
    abi: artifact.abi,
    functionName: "committeeRetired",
  }) as boolean;
  if (remainingAfter !== 0n || !retiredAfter) {
    throw new Error(`${item.scenario.mode}: settlement state mismatch.`);
  }

  settlements.push({
    mode: item.scenario.mode,
    contractAddress: item.scenario.contractAddress,
    recipient: ownerAddress,
    amountWei: item.remainingBond.toString(),
    transactionHash: hash as Hex,
    blockNumber: receipt.blockNumber.toString(),
    blockHash: receipt.blockHash,
    gasUsed: receipt.gasUsed.toString(),
    effectiveGasPrice: receipt.effectiveGasPrice.toString(),
    gasCostWei: (
      receipt.gasUsed * receipt.effectiveGasPrice
    ).toString(),
  });
}

const result = {
  schema: "fc-trace-then-slash-phase2-settlement-v1",
  generatedAt: new Date().toISOString(),
  network: { name: "Chiado", chainId: 10200, confirmations: CONFIRMATIONS },
  owner: ownerAddress,
  settlements,
};
await mkdir(resolve(root, "results"), { recursive: true });
const output = resolve(root, "results/phase2_settlement.json");
await writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(`PHASE2_SETTLEMENT_RESULT=${output}`);
console.log("PHASE2_REMAINING_BONDS_RECOVERED=PASS");
