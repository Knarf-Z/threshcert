import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { network } from "hardhat";
import {
  hashTypedData,
  keccak256,
  parseEther,
  stringToHex,
  type Abi,
  type Address,
  type Hex,
} from "viem";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

import {
  earlyShareArtifactTypes,
  earlyShareEvidenceTypes,
  traceThenSlashDomain,
  type EarlyShareArtifact,
} from "../src/evidence.js";

const EXECUTION_GUARD = "I_UNDERSTAND_PUBLIC_TRANSACTIONS";
const COMMITTEE_SIZE = 7;
const THRESHOLD = 4;
const CALLER_REWARD = parseEther("0.1");
const TARGET_MEMBERS = [0, 1, 2, 3] as const;
const MODES = ["sequential", "atomic_package", "repeated_packages"] as const;
const CONFIRMATIONS = Number(process.env.PHASE2_CONFIRMATIONS ?? "2");
const BOND = parseEther(process.env.PHASE2_BOND_NATIVE ?? "2");

type Mode = (typeof MODES)[number];
type SignedEvidence = EarlyShareArtifact & {
  memberSignature: Hex;
  verifierSignature: Hex;
  evidenceDigest: Hex;
};
type ArtifactFile = {
  abi: Abi;
  bytecode: Hex;
};
type TransactionRecord = {
  label: string;
  hash: Hex;
  blockNumber: string;
  blockHash: Hex;
  status: string;
  gasUsed: string;
};

if (process.env.PHASE2_EXECUTE !== EXECUTION_GUARD) {
  throw new Error(
    `Refusing public-chain writes. Set PHASE2_EXECUTE=${EXECUTION_GUARD} only after checking the RPC, deployer, balance, and bond amount.`,
  );
}
if (BOND !== parseEther("2")) {
  throw new Error(
    "The paper-matched Phase 2 run requires PHASE2_BOND_NATIVE=2 exactly.",
  );
}
if (!Number.isInteger(CONFIRMATIONS) || CONFIRMATIONS < 1) {
  throw new Error("PHASE2_CONFIRMATIONS must be a positive integer.");
}

const root = resolve(import.meta.dirname, "..");
const artifactPath = resolve(
  root,
  "artifacts/contracts/TraceThenSlash.sol/TraceThenSlash.json",
);
const artifact = JSON.parse(
  await readFile(artifactPath, "utf8"),
) as ArtifactFile;
const source = await readFile(resolve(root, "contracts/TraceThenSlash.sol"));

const connection = await network.connect();
const { viem } = connection;
const publicClient = await viem.getPublicClient();
const wallets = await viem.getWalletClients();
const owner = wallets[0];
if (owner?.account === undefined) {
  throw new Error("Chiado deployer account is unavailable.");
}
const chainId = await publicClient.getChainId();
if (chainId !== 10200) {
  throw new Error(`Expected Chiado chain id 10200, received ${chainId}.`);
}

const ownerAddress = owner.account.address;
const startingBalance = await publicClient.getBalance({
  address: ownerAddress,
});
const lockedPrincipal = BOND * BigInt(COMMITTEE_SIZE * MODES.length);
const gasReserve = parseEther("0.5");
if (startingBalance < lockedPrincipal + gasReserve) {
  throw new Error(
    `Insufficient deployer balance: need at least ${lockedPrincipal + gasReserve} wei before gas/refunds; have ${startingBalance} wei.`,
  );
}

async function waitFor(
  label: string,
  hash: Hex,
): Promise<TransactionRecord> {
  const receipt = await publicClient.waitForTransactionReceipt({
    hash,
    confirmations: CONFIRMATIONS,
  });
  if (receipt.status !== "success") {
    throw new Error(`${label} reverted: ${hash}`);
  }
  return {
    label,
    hash,
    blockNumber: receipt.blockNumber.toString(),
    blockHash: receipt.blockHash,
    status: receipt.status,
    gasUsed: receipt.gasUsed.toString(),
  };
}

async function writeContract(
  address: Address,
  functionName: string,
  args: readonly unknown[],
  label: string,
  value?: bigint,
): Promise<TransactionRecord> {
  const hash = await owner.writeContract({
    account: owner.account,
    address,
    abi: artifact.abi,
    functionName,
    args,
    value,
  });
  return waitFor(label, hash);
}

async function readContract<T>(
  address: Address,
  functionName: string,
  args: readonly unknown[] = [],
): Promise<T> {
  return publicClient.readContract({
    address,
    abi: artifact.abi,
    functionName,
    args,
  }) as Promise<T>;
}

async function runScenario(mode: Mode) {
  const verifierAccount = privateKeyToAccount(generatePrivateKey());
  const treasuryAccount = privateKeyToAccount(generatePrivateKey());
  const memberAccounts = Array.from({ length: COMMITTEE_SIZE }, () =>
    privateKeyToAccount(generatePrivateKey()),
  );
  const transactions: TransactionRecord[] = [];

  const deployHash = await owner.deployContract({
    account: owner.account,
    abi: artifact.abi,
    bytecode: artifact.bytecode,
    args: [
      ownerAddress,
      verifierAccount.address,
      treasuryAccount.address,
      CALLER_REWARD,
    ],
  });
  const deployment = await waitFor(`${mode}:deploy`, deployHash);
  transactions.push(deployment);
  const deployReceipt = await publicClient.getTransactionReceipt({
    hash: deployHash,
  });
  const contractAddress = deployReceipt.contractAddress;
  if (contractAddress === null || contractAddress === undefined) {
    throw new Error(`${mode}: deployment receipt has no contract address.`);
  }

  for (let index = 0; index < COMMITTEE_SIZE; index += 1) {
    transactions.push(
      await writeContract(
        contractAddress,
        "registerMember",
        [index, memberAccounts[index].address],
        `${mode}:register:${index}`,
        BOND,
      ),
    );
  }
  transactions.push(
    await writeContract(
      contractAddress,
      "freezeCommittee",
      [],
      `${mode}:freeze`,
    ),
  );

  const initialCertificate = await readContract<bigint>(
    contractAddress,
    "frozenThresholdBondFloor",
  );
  const initialTotalBond = await readContract<bigint>(
    contractAddress,
    "totalBond",
  );
  const latest = await publicClient.getBlock();
  const releaseTime = latest.timestamp + 604_800n;
  const identityHash = keccak256(
    stringToHex(`rq3-phase2-chiado-${mode}-${contractAddress}`),
  );
  transactions.push(
    await writeContract(
      contractAddress,
      "openRelease",
      [1n, identityHash, releaseTime],
      `${mode}:open-release`,
    ),
  );
  const nonce = await readContract<bigint>(
    contractAddress,
    "jobCount",
  );
  const jobId = await readContract<Hex>(
    contractAddress,
    "computeJobId",
    [1n, identityHash, releaseTime, nonce],
  );

  const evidence: SignedEvidence[] = [];
  for (const memberIndex of TARGET_MEMBERS) {
    const artifactMessage: EarlyShareArtifact = {
      jobId,
      memberIndex,
      shareHash: keccak256(
        stringToHex(
          `covered-chiado-share-${mode}-${memberIndex}-${contractAddress}`,
        ),
      ),
    };
    const memberSignature = await memberAccounts[memberIndex].signTypedData({
      domain: traceThenSlashDomain(chainId, contractAddress),
      types: earlyShareArtifactTypes,
      primaryType: "EarlyShareArtifact",
      message: artifactMessage,
    });
    const memberSignatureHash = keccak256(memberSignature);
    const verifierSignature = await verifierAccount.signTypedData({
      domain: traceThenSlashDomain(chainId, contractAddress),
      types: earlyShareEvidenceTypes,
      primaryType: "EarlyShareEvidence",
      message: { ...artifactMessage, memberSignatureHash },
    });
    const evidenceDigest = hashTypedData({
      domain: traceThenSlashDomain(chainId, contractAddress),
      types: earlyShareEvidenceTypes,
      primaryType: "EarlyShareEvidence",
      message: { ...artifactMessage, memberSignatureHash },
    });
    evidence.push({
      ...artifactMessage,
      memberSignature,
      verifierSignature,
      evidenceDigest,
    });
  }

  const packageArgs = (slice: SignedEvidence[]) =>
    [
      slice.map((item) => item.jobId),
      slice.map((item) => item.memberIndex),
      slice.map((item) => item.shareHash),
      slice.map((item) => item.memberSignature),
      slice.map((item) => item.verifierSignature),
    ] as const;

  const slashTransactions: TransactionRecord[] = [];
  if (mode === "sequential") {
    for (const item of evidence) {
      slashTransactions.push(
        await writeContract(
          contractAddress,
          "slashEarlyShare",
          [
            item.jobId,
            item.memberIndex,
            item.shareHash,
            item.memberSignature,
            item.verifierSignature,
          ],
          `${mode}:slash:${item.memberIndex}`,
        ),
      );
    }
  } else if (mode === "atomic_package") {
    slashTransactions.push(
      await writeContract(
        contractAddress,
        "slashPackage",
        packageArgs(evidence),
        `${mode}:slash:0-3`,
      ),
    );
  } else {
    slashTransactions.push(
      await writeContract(
        contractAddress,
        "slashPackage",
        packageArgs(evidence.slice(0, 2)),
        `${mode}:slash:0-1`,
      ),
    );
    slashTransactions.push(
      await writeContract(
        contractAddress,
        "slashPackage",
        packageArgs(evidence.slice(2, 4)),
        `${mode}:slash:2-3`,
      ),
    );
  }
  transactions.push(...slashTransactions);

  const postAttackCertificate = await readContract<bigint>(
    contractAddress,
    "currentCertificate",
  );
  const remainingBond = await readContract<bigint>(
    contractAddress,
    "totalBond",
  );
  const callerRewardBeforeWithdrawal = await readContract<bigint>(
    contractAddress,
    "claimableRewards",
    [ownerAddress],
  );
  const treasuryAccrual = await readContract<bigint>(
    contractAddress,
    "treasuryAccrued",
  );
  const realizedMemberLoss = initialTotalBond - remainingBond;

  const withdrawal = await writeContract(
    contractAddress,
    "withdrawReward",
    [ownerAddress],
    `${mode}:withdraw-reward`,
  );
  transactions.push(withdrawal);
  const callerRewardAfterWithdrawal = await readContract<bigint>(
    contractAddress,
    "claimableRewards",
    [ownerAddress],
  );
  const onChainCode = await publicClient.getCode({
    address: contractAddress,
  });
  if (onChainCode === undefined || onChainCode === "0x") {
    throw new Error(`${mode}: deployed bytecode is empty.`);
  }

  return {
    mode,
    chainId,
    contractAddress,
    constructor: {
      owner: ownerAddress,
      verifier: verifierAccount.address,
      treasury: treasuryAccount.address,
      callerRewardWeiPerSlash: CALLER_REWARD.toString(),
    },
    deployTransactionHash: deployHash,
    deployedCodeKeccak256: keccak256(onChainCode),
    memberSignerAddresses: memberAccounts.map((item) => item.address),
    submitter: ownerAddress,
    job: {
      jobId,
      eon: "1",
      identityHash,
      releaseTime: releaseTime.toString(),
      nonce: nonce.toString(),
    },
    grouping:
      mode === "sequential" ? [1, 1, 1, 1] :
      mode === "atomic_package" ? [4] :
      [2, 2],
    evidence,
    initialTotalBondWei: initialTotalBond.toString(),
    preAttackThresholdBondFloorWei: initialCertificate.toString(),
    realizedMemberLossWei: realizedMemberLoss.toString(),
    callerRewardAccruedWei: callerRewardBeforeWithdrawal.toString(),
    callerRewardAfterWithdrawalWei: callerRewardAfterWithdrawal.toString(),
    treasuryAccruedWei: treasuryAccrual.toString(),
    remainingBondWei: remainingBond.toString(),
    postAttackCurrentCertificateWei: postAttackCertificate.toString(),
    slashTransactionHashes: slashTransactions.map((item) => item.hash),
    rewardWithdrawalTransactionHash: withdrawal.hash,
    transactions,
  };
}

const scenarios = [];
for (const mode of MODES) {
  console.log(`phase2_start=${mode}`);
  scenarios.push(await runScenario(mode));
  console.log(`phase2_complete=${mode}`);
}

const endingBalance = await publicClient.getBalance({ address: ownerAddress });
const result = {
  schema: "fc-trace-then-slash-phase2-chiado-v1",
  generatedAt: new Date().toISOString(),
  status: "PUBLIC_SCOPED_EXECUTION",
  network: {
    name: "Chiado",
    chainId,
    confirmations: CONFIRMATIONS,
    rpcEndpointPublished: false,
  },
  environment: {
    controlledKeys: true,
    independentOperators: false,
    productionDeployment: false,
    publicReceipts: true,
    independentRpcVerificationSupported: true,
  },
  committee: {
    size: COMMITTEE_SIZE,
    threshold: THRESHOLD,
    bondWeiPerMember: BOND.toString(),
    callerRewardWeiPerSlash: CALLER_REWARD.toString(),
  },
  certificate: {
    type: "enforcement-loss",
    lowerBoundWei: (BOND * BigInt(THRESHOLD)).toString(),
    unit: "Chiado native wei",
    packageSizeParameterB: "not used",
    statement:
      "Three public controlled instances realize the same four-member enforcement loss under sequential, one-package, and repeated-package submission. This is not by itself an attacker-payment or production-security certificate.",
  },
  source: {
    contractSourceSha256: createHash("sha256").update(source).digest("hex"),
    creationBytecodeKeccak256: keccak256(artifact.bytecode),
    compiler: "solc 0.8.28, optimizer 200 runs, viaIR, Cancun",
  },
  deployer: {
    address: ownerAddress,
    startingBalanceWei: startingBalance.toString(),
    endingBalanceWei: endingBalance.toString(),
  },
  scenarios,
};

await mkdir(resolve(root, "results"), { recursive: true });
const output = resolve(root, "results/phase2_chiado.json");
await writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(`PHASE2_RESULT=${output}`);
console.log("PHASE2_PUBLIC_PACKAGE_INVARIANCE=PASS");
