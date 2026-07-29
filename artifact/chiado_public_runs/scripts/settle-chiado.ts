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
const RUN_FILES = [
  { sourceRun: "calibration", file: "phase2_chiado_underfunded_run1.json" },
  { sourceRun: "covered", file: "phase2_chiado_covered_run2.json" },
] as const;

const root = resolve(import.meta.dirname, "..");
const output = resolve(root, "results/phase2_settlement.json");

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
type TaggedScenario = Scenario & {
  sourceRun: (typeof RUN_FILES)[number]["sourceRun"];
  sourceFile: string;
};
type SettlementRecord = {
  sourceRun: TaggedScenario["sourceRun"];
  sourceFile: string;
  mode: string;
  contractAddress: Address;
  recipient: Address;
  amountWei: string;
  transactionHash: Hex;
  blockNumber: string;
  blockHash: Hex;
  gasUsed: string;
  effectiveGasPrice: string;
  gasCostWei: string;
};

if (process.env.PHASE2_SETTLE !== SETTLEMENT_GUARD) {
  throw new Error(
    `Refusing public-chain settlement. Set PHASE2_SETTLE=${SETTLEMENT_GUARD} only after all recorded release windows have ended.`,
  );
}
if (!Number.isInteger(CONFIRMATIONS) || CONFIRMATIONS < 1) {
  throw new Error("PHASE2_CONFIRMATIONS must be a positive integer.");
}

const taggedScenarios: TaggedScenario[] = [];
for (const run of RUN_FILES) {
  const deployment = JSON.parse(
    await readFile(resolve(root, "results", run.file), "utf8"),
  ) as DeploymentResult;
  if (deployment.schema !== "fc-trace-then-slash-phase2-chiado-v2") {
    throw new Error(`${run.sourceRun}: unexpected deployment result schema.`);
  }
  if (deployment.network.chainId !== 10200) {
    throw new Error(`${run.sourceRun}: result is not for Chiado.`);
  }
  for (const scenario of deployment.scenarios) {
    taggedScenarios.push({ ...scenario, sourceRun: run.sourceRun, sourceFile: run.file });
  }
}
if (taggedScenarios.length !== 6) {
  throw new Error(`Expected six contracts across two preserved runs, found ${taggedScenarios.length}.`);
}
const addressKeys = taggedScenarios.map((scenario) => scenario.contractAddress.toLowerCase());
if (new Set(addressKeys).size !== taggedScenarios.length) {
  throw new Error("Duplicate contract address across preserved runs.");
}
const expectedTotalWei = taggedScenarios.reduce(
  (sum, scenario) => sum + BigInt(scenario.remainingBondWei),
  0n,
);
if (expectedTotalWei !== 108000000000000000n) {
  throw new Error(`Unexpected aggregate remaining bond: ${expectedTotalWei}.`);
}

const artifact = JSON.parse(
  await readFile(
    resolve(root, "artifacts/contracts/TraceThenSlash.sol/TraceThenSlash.json"),
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

for (const scenario of taggedScenarios) {
  if (scenario.constructor.owner.toLowerCase() !== ownerAddress.toLowerCase()) {
    throw new Error(
      `${scenario.sourceRun}/${scenario.mode}: connected account is not the owner.`,
    );
  }
}

const records = new Map<string, SettlementRecord>();
try {
  const previous = JSON.parse(await readFile(output, "utf8")) as {
    settlements?: SettlementRecord[];
  };
  for (const record of previous.settlements ?? []) {
    records.set(record.contractAddress.toLowerCase(), record);
  }
} catch (error) {
  const code = (error as NodeJS.ErrnoException).code;
  if (code !== "ENOENT") throw error;
}

async function recordFromChain(scenario: TaggedScenario): Promise<SettlementRecord> {
  const logs = await publicClient.getContractEvents({
    address: scenario.contractAddress,
    abi: artifact.abi,
    eventName: "RemainingBondsWithdrawn",
    fromBlock: 0n,
    toBlock: "latest",
  });
  const matching = logs.filter((log) => {
    const args = log.args as { recipient?: Address; amount?: bigint };
    return args.recipient?.toLowerCase() === ownerAddress.toLowerCase()
      && args.amount === BigInt(scenario.remainingBondWei);
  });
  if (matching.length !== 1 || matching[0].transactionHash === null) {
    throw new Error(
      `${scenario.sourceRun}/${scenario.mode}: retired contract lacks one auditable withdrawal event.`,
    );
  }
  const receipt = await publicClient.getTransactionReceipt({
    hash: matching[0].transactionHash,
  });
  return {
    sourceRun: scenario.sourceRun,
    sourceFile: scenario.sourceFile,
    mode: scenario.mode,
    contractAddress: scenario.contractAddress,
    recipient: ownerAddress,
    amountWei: scenario.remainingBondWei,
    transactionHash: matching[0].transactionHash,
    blockNumber: receipt.blockNumber.toString(),
    blockHash: receipt.blockHash,
    gasUsed: receipt.gasUsed.toString(),
    effectiveGasPrice: receipt.effectiveGasPrice.toString(),
    gasCostWei: (receipt.gasUsed * receipt.effectiveGasPrice).toString(),
  };
}

async function persist(): Promise<void> {
  const settlements = taggedScenarios
    .map((scenario) => records.get(scenario.contractAddress.toLowerCase()))
    .filter((record): record is SettlementRecord => record !== undefined);
  const recoveredTotalWei = settlements.reduce(
    (sum, record) => sum + BigInt(record.amountWei),
    0n,
  );
  const result = {
    schema: "fc-trace-then-slash-phase2-settlement-v2",
    generatedAt: new Date().toISOString(),
    network: { name: "Chiado", chainId: 10200, confirmations: CONFIRMATIONS },
    owner: ownerAddress,
    sourceRuns: RUN_FILES,
    expectedContracts: taggedScenarios.length,
    expectedTotalWei: expectedTotalWei.toString(),
    recoveredContracts: settlements.length,
    recoveredTotalWei: recoveredTotalWei.toString(),
    complete: settlements.length === taggedScenarios.length
      && recoveredTotalWei === expectedTotalWei,
    settlements,
  };
  await mkdir(resolve(root, "results"), { recursive: true });
  await writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

const latestBlock = await publicClient.getBlock();
const pending: Array<{
  scenario: TaggedScenario;
  latestReleaseTime: bigint;
  remainingBond: bigint;
}> = [];

for (const scenario of taggedScenarios) {
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
    if (remainingBond !== 0n) {
      throw new Error(`${scenario.sourceRun}/${scenario.mode}: retired contract retains a bond.`);
    }
    if (!records.has(scenario.contractAddress.toLowerCase())) {
      records.set(scenario.contractAddress.toLowerCase(), await recordFromChain(scenario));
    }
    continue;
  }
  if (remainingBond !== BigInt(scenario.remainingBondWei)) {
    throw new Error(`${scenario.sourceRun}/${scenario.mode}: remaining bond differs from the preserved run.`);
  }
  if (latestBlock.timestamp < latestReleaseTime) {
    throw new Error(
      `${scenario.sourceRun}/${scenario.mode}: release window remains active until ${new Date(
        Number(latestReleaseTime) * 1000,
      ).toISOString()}.`,
    );
  }
  pending.push({ scenario, latestReleaseTime, remainingBond });
}

await persist();
for (const item of pending) {
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
    throw new Error(`${item.scenario.sourceRun}/${item.scenario.mode}: settlement reverted: ${hash}`);
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
    throw new Error(`${item.scenario.sourceRun}/${item.scenario.mode}: settlement state mismatch.`);
  }

  records.set(item.scenario.contractAddress.toLowerCase(), {
    sourceRun: item.scenario.sourceRun,
    sourceFile: item.scenario.sourceFile,
    mode: item.scenario.mode,
    contractAddress: item.scenario.contractAddress,
    recipient: ownerAddress,
    amountWei: item.remainingBond.toString(),
    transactionHash: hash as Hex,
    blockNumber: receipt.blockNumber.toString(),
    blockHash: receipt.blockHash,
    gasUsed: receipt.gasUsed.toString(),
    effectiveGasPrice: receipt.effectiveGasPrice.toString(),
    gasCostWei: (receipt.gasUsed * receipt.effectiveGasPrice).toString(),
  });
  await persist();
}

await persist();
if (records.size !== taggedScenarios.length) {
  throw new Error(`Recovered ${records.size} of ${taggedScenarios.length} contracts.`);
}
const recoveredTotalWei = [...records.values()].reduce(
  (sum, record) => sum + BigInt(record.amountWei),
  0n,
);
if (recoveredTotalWei !== expectedTotalWei) {
  throw new Error(`Recovered ${recoveredTotalWei} wei, expected ${expectedTotalWei}.`);
}

console.log(`PHASE2_SETTLEMENT_RESULT=${output}`);
console.log(`PHASE2_SETTLED_CONTRACTS=${records.size}`);
console.log(`PHASE2_RECOVERED_TOTAL_WEI=${recoveredTotalWei}`);
console.log("PHASE2_REMAINING_BONDS_RECOVERED=PASS");