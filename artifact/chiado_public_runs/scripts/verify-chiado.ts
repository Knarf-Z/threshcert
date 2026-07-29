import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import {
  createPublicClient,
  decodeEventLog,
  encodeDeployData,
  hashTypedData,
  http,
  keccak256,
  recoverTypedDataAddress,
  type Abi,
  type Address,
  type Hex,
  type TransactionReceipt,
} from "viem";

import {
  earlyShareArtifactTypes,
  earlyShareEvidenceTypes,
  traceThenSlashDomain,
} from "../src/evidence.js";

type ArtifactFile = { abi: Abi; bytecode: Hex };
type EvidenceRecord = {
  jobId: Hex;
  memberIndex: number;
  shareHash: Hex;
  memberSignature: Hex;
  verifierSignature: Hex;
  evidenceDigest: Hex;
};
type TransactionRecord = {
  label: string;
  hash: Hex;
  from: Address;
  to: Address | null;
  blockNumber: string;
  blockHash: Hex;
  status: string;
  gasUsed: string;
  effectiveGasPrice: string;
  gasCostWei: string;
};
type Scenario = {
  mode: "sequential" | "atomic_package" | "repeated_packages";
  chainId: number;
  contractAddress: Address;
  constructor: {
    owner: Address;
    verifier: Address;
    treasury: Address;
    callerRewardWeiPerSlash: string;
  };
  deployTransactionHash: Hex;
  deployedCodeKeccak256: Hex;
  memberSignerAddresses: Address[];
  submitter: Address;
  job: {
    jobId: Hex;
    eon: string;
    identityHash: Hex;
    releaseTime: string;
    nonce: string;
  };
  grouping: number[];
  evidence: EvidenceRecord[];
  initialTotalBondWei: string;
  preAttackThresholdBondFloorWei: string;
  realizedCoveredBondLossWei: string;
  callerRewardAccruedWei: string;
  callerRewardAfterWithdrawalWei: string;
  treasuryAccruedBeforeWithdrawalWei: string;
  treasuryAccruedAfterWithdrawalWei: string;
  remainingBondWei: string;
  postAttackCurrentCertificateWei: string;
  enforcementGasCostWei: string;
  rewardCoversEnforcementGas: boolean;
  netCallerSurplusWei: string;
  slashTransactionHashes: Hex[];
  rewardWithdrawalTransactionHash: Hex;
  treasuryWithdrawalTransactionHash: Hex;
  snapshotBlockNumber: string;
  transactions: TransactionRecord[];
};
type Result = {
  schema: string;
  status: string;
  network: { chainId: number };
  environment: {
    independentOperators: boolean;
    productionDeployment: boolean;
    publicReceipts: boolean;
    independentRpcVerificationSupported: boolean;
  };
  committee: {
    size: number;
    threshold: number;
    bondWeiPerMember: string;
    callerRewardWeiPerSlash: string;
  };
  certificate: {
    type: string;
    lowerBoundWei: string;
    packageSizeParameterB: string;
  };
  source: {
    contractSourceSha256: string;
    creationBytecodeKeccak256: Hex;
  };
  scenarios: Scenario[];
};

type EarlySlashArgs = {
  memberLoss: bigint;
  callerReward: bigint;
  treasuryAccrual: bigint;
};
type PackageSlashArgs = {
  evidenceCount: bigint;
  totalMemberLoss: bigint;
  totalCallerReward: bigint;
  totalTreasuryAccrual: bigint;
};
type WithdrawalArgs = { recipient: Address; amount: bigint };

function require(condition: boolean, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function equalAddress(left: Address, right: Address): boolean {
  return left.toLowerCase() === right.toLowerCase();
}

const root = resolve(import.meta.dirname, "..");
const rpcUrl = process.env.CHIADO_VERIFY_RPC_URL;
if (rpcUrl === undefined || rpcUrl.length === 0) {
  throw new Error(
    "Set CHIADO_VERIFY_RPC_URL explicitly to an independent archive-capable Chiado RPC.",
  );
}
if (
  process.env.CHIADO_RPC_URL !== undefined &&
  process.env.CHIADO_RPC_URL === rpcUrl
) {
  throw new Error(
    "CHIADO_VERIFY_RPC_URL must differ from the deployment RPC endpoint.",
  );
}

const result = JSON.parse(
  await readFile(resolve(root, "results/phase2_chiado.json"), "utf8"),
) as Result;
const artifact = JSON.parse(
  await readFile(
    resolve(
      root,
      "artifacts/contracts/TraceThenSlash.sol/TraceThenSlash.json",
    ),
    "utf8",
  ),
) as ArtifactFile;
const source = await readFile(resolve(root, "contracts/TraceThenSlash.sol"));

require(
  result.schema === "fc-trace-then-slash-phase2-chiado-v2",
  "Unexpected result schema.",
);
require(result.status === "PUBLIC_SCOPED_EXECUTION", "Run is not complete.");
require(result.network.chainId === 10200, "Result is not for Chiado.");
require(result.environment.publicReceipts, "Public receipts were not claimed.");
require(
  result.environment.independentRpcVerificationSupported,
  "Independent RPC verification was not enabled.",
);
require(!result.environment.independentOperators, "Scope drift.");
require(!result.environment.productionDeployment, "Scope drift.");
require(result.committee.size === 7, "Wrong committee size.");
require(result.committee.threshold === 4, "Wrong threshold.");
require(result.certificate.type === "enforcement-loss", "Wrong certificate type.");
require(
  result.certificate.packageSizeParameterB === "not used",
  "External package bound was reintroduced.",
);
require(
  createHash("sha256").update(source).digest("hex") ===
    result.source.contractSourceSha256,
  "Contract source hash mismatch.",
);
require(
  keccak256(artifact.bytecode) === result.source.creationBytecodeKeccak256,
  "Creation bytecode hash mismatch.",
);

const client = createPublicClient({ transport: http(rpcUrl) });
require((await client.getChainId()) === 10200, "RPC is not Chiado.");

const bond = BigInt(result.committee.bondWeiPerMember);
const rewardPerSlash = BigInt(result.committee.callerRewardWeiPerSlash);
const expectedLoss = bond * 4n;
const expectedReward = rewardPerSlash * 4n;
const expectedTreasury = expectedLoss - expectedReward;
require(rewardPerSlash > 0n && rewardPerSlash < bond, "Invalid reward amount.");
require(
  BigInt(result.certificate.lowerBoundWei) === expectedLoss,
  "Certificate amount mismatch.",
);

const expectedGroupings = new Map([
  ["sequential", "1,1,1,1"],
  ["atomic_package", "4"],
  ["repeated_packages", "2,2"],
]);
require(result.scenarios.length === 3, "Expected exactly three scenarios.");

for (const scenario of result.scenarios) {
  require(scenario.chainId === 10200, `${scenario.mode}: wrong chain id.`);
  require(
    scenario.grouping.join(",") === expectedGroupings.get(scenario.mode),
    `${scenario.mode}: wrong grouping.`,
  );
  require(
    equalAddress(scenario.constructor.owner, scenario.submitter),
    `${scenario.mode}: owner/submitter mismatch.`,
  );
  require(
    equalAddress(scenario.constructor.treasury, scenario.constructor.owner),
    `${scenario.mode}: treasury is not recoverable by the owner.`,
  );
  require(
    !scenario.memberSignerAddresses.some((item) =>
      equalAddress(item, scenario.submitter)
    ),
    `${scenario.mode}: submitter is a registered member.`,
  );
  require(
    scenario.transactions.length === 12 + scenario.grouping.length,
    `${scenario.mode}: unexpected transaction count.`,
  );

  const receiptByHash = new Map<string, TransactionReceipt>();
  const enforcementHashes = new Set(
    [
      ...scenario.slashTransactionHashes,
      scenario.rewardWithdrawalTransactionHash,
    ].map((hash) => hash.toLowerCase()),
  );
  let observedEnforcementGasCost = 0n;

  for (const transaction of scenario.transactions) {
    const receipt = await client.getTransactionReceipt({
      hash: transaction.hash,
    });
    const chainTransaction = await client.getTransaction({
      hash: transaction.hash,
    });
    receiptByHash.set(transaction.hash.toLowerCase(), receipt);

    require(receipt.status === "success", `${transaction.label}: failed.`);
    require(
      equalAddress(receipt.from, transaction.from),
      `${transaction.label}: receipt sender mismatch.`,
    );
    require(
      equalAddress(chainTransaction.from, transaction.from),
      `${transaction.label}: transaction sender mismatch.`,
    );
    require(
      receipt.blockNumber.toString() === transaction.blockNumber,
      `${transaction.label}: block number mismatch.`,
    );
    require(
      receipt.blockHash.toLowerCase() === transaction.blockHash.toLowerCase(),
      `${transaction.label}: block hash mismatch.`,
    );
    require(
      receipt.gasUsed.toString() === transaction.gasUsed,
      `${transaction.label}: gas-used mismatch.`,
    );
    require(
      receipt.effectiveGasPrice.toString() === transaction.effectiveGasPrice,
      `${transaction.label}: effective-gas-price mismatch.`,
    );
    const gasCost = receipt.gasUsed * receipt.effectiveGasPrice;
    require(
      gasCost.toString() === transaction.gasCostWei,
      `${transaction.label}: gas-cost mismatch.`,
    );

    if (transaction.hash.toLowerCase() ===
        scenario.deployTransactionHash.toLowerCase()) {
      require(receipt.to === null, `${transaction.label}: deployment has a to.`);
      require(chainTransaction.to === null, `${transaction.label}: invalid deploy.`);
    } else {
      require(
        receipt.to !== null && equalAddress(receipt.to, scenario.contractAddress),
        `${transaction.label}: receipt target mismatch.`,
      );
      require(
        chainTransaction.to !== null &&
          equalAddress(chainTransaction.to, scenario.contractAddress),
        `${transaction.label}: transaction target mismatch.`,
      );
    }
    if (enforcementHashes.has(transaction.hash.toLowerCase())) {
      observedEnforcementGasCost += gasCost;
    }
  }

  const deploymentReceipt = receiptByHash.get(
    scenario.deployTransactionHash.toLowerCase(),
  );
  require(deploymentReceipt !== undefined, `${scenario.mode}: missing deploy receipt.`);
  require(
    deploymentReceipt.contractAddress !== null &&
      deploymentReceipt.contractAddress !== undefined &&
      equalAddress(deploymentReceipt.contractAddress, scenario.contractAddress),
    `${scenario.mode}: deployment contract address mismatch.`,
  );

  const deploymentTransaction = await client.getTransaction({
    hash: scenario.deployTransactionHash,
  });
  const expectedDeployData = encodeDeployData({
    abi: artifact.abi,
    bytecode: artifact.bytecode,
    args: [
      scenario.constructor.owner,
      scenario.constructor.verifier,
      scenario.constructor.treasury,
      BigInt(scenario.constructor.callerRewardWeiPerSlash),
    ],
  });
  require(
    deploymentTransaction.input.toLowerCase() ===
      expectedDeployData.toLowerCase(),
    `${scenario.mode}: deployment input does not match the local artifact.`,
  );

  const snapshotBlock = BigInt(scenario.snapshotBlockNumber);
  const maximumRecordedBlock = scenario.transactions.reduce(
    (maximum, transaction) => {
      const block = BigInt(transaction.blockNumber);
      return block > maximum ? block : maximum;
    },
    0n,
  );
  require(
    snapshotBlock === maximumRecordedBlock,
    `${scenario.mode}: snapshot is not the terminal run block.`,
  );

  const code = await client.getCode({
    address: scenario.contractAddress,
    blockNumber: snapshotBlock,
  });
  require(code !== undefined && code !== "0x", `${scenario.mode}: empty code.`);
  require(
    keccak256(code).toLowerCase() ===
      scenario.deployedCodeKeccak256.toLowerCase(),
    `${scenario.mode}: deployed bytecode hash mismatch.`,
  );

  const read = async <T>(
    functionName: string,
    args: readonly unknown[] = [],
  ): Promise<T> =>
    client.readContract({
      address: scenario.contractAddress,
      abi: artifact.abi,
      functionName,
      args,
      blockNumber: snapshotBlock,
    }) as Promise<T>;

  require(
    equalAddress(await read<Address>("owner"), scenario.constructor.owner),
    `${scenario.mode}: owner mismatch.`,
  );
  require(
    equalAddress(await read<Address>("verifier"), scenario.constructor.verifier),
    `${scenario.mode}: verifier mismatch.`,
  );
  require(
    equalAddress(await read<Address>("treasury"), scenario.constructor.treasury),
    `${scenario.mode}: treasury mismatch.`,
  );
  require(await read<boolean>("committeeFrozen"), `${scenario.mode}: not frozen.`);
  require(
    !(await read<boolean>("committeeRetired")),
    `${scenario.mode}: retired during the measured run.`,
  );
  require(
    (await read<bigint>("latestReleaseTime")).toString() ===
      scenario.job.releaseTime,
    `${scenario.mode}: latest release time mismatch.`,
  );
  require(
    await read<bigint>("frozenThresholdBondFloor") ===
      BigInt(scenario.preAttackThresholdBondFloorWei),
    `${scenario.mode}: frozen floor mismatch.`,
  );
  require(
    await read<bigint>("totalBond") === BigInt(scenario.remainingBondWei),
    `${scenario.mode}: remaining bond mismatch.`,
  );
  require(
    await read<bigint>("currentCertificate") ===
      BigInt(scenario.postAttackCurrentCertificateWei),
    `${scenario.mode}: current certificate mismatch.`,
  );
  require(
    await read<bigint>("treasuryAccrued") ===
      BigInt(scenario.treasuryAccruedAfterWithdrawalWei),
    `${scenario.mode}: post-withdrawal treasury mismatch.`,
  );
  require(
    await read<bigint>("claimableRewards", [scenario.submitter]) ===
      BigInt(scenario.callerRewardAfterWithdrawalWei),
    `${scenario.mode}: post-withdrawal reward mismatch.`,
  );

  for (let index = 0; index < 7; index += 1) {
    const member = await read<
      readonly [Address, bigint, boolean, boolean]
    >("members", [index]);
    require(
      equalAddress(member[0], scenario.memberSignerAddresses[index]),
      `${scenario.mode}: member ${index} signer mismatch.`,
    );
    require(member[2], `${scenario.mode}: member ${index} not registered.`);
    require(
      member[3] === (index < 4),
      `${scenario.mode}: member ${index} slash state mismatch.`,
    );
    require(
      member[1] === (index < 4 ? 0n : bond),
      `${scenario.mode}: member ${index} bond mismatch.`,
    );
  }

  const job = await read<
    readonly [bigint, bigint, Hex, boolean]
  >("jobs", [scenario.job.jobId]);
  require(job[3], `${scenario.mode}: job missing.`);
  require(job[0].toString() === scenario.job.eon, `${scenario.mode}: eon mismatch.`);
  require(
    job[1].toString() === scenario.job.releaseTime,
    `${scenario.mode}: release time mismatch.`,
  );
  require(
    job[2].toLowerCase() === scenario.job.identityHash.toLowerCase(),
    `${scenario.mode}: identity hash mismatch.`,
  );

  for (const evidence of scenario.evidence) {
    const domain = traceThenSlashDomain(10200, scenario.contractAddress);
    const recoveredMember = await recoverTypedDataAddress({
      domain,
      types: earlyShareArtifactTypes,
      primaryType: "EarlyShareArtifact",
      message: {
        jobId: evidence.jobId,
        memberIndex: evidence.memberIndex,
        shareHash: evidence.shareHash,
      },
      signature: evidence.memberSignature,
    });
    require(
      equalAddress(
        recoveredMember,
        scenario.memberSignerAddresses[evidence.memberIndex],
      ),
      `${scenario.mode}: member signature mismatch.`,
    );
    const memberSignatureHash = keccak256(evidence.memberSignature);
    const recoveredVerifier = await recoverTypedDataAddress({
      domain,
      types: earlyShareEvidenceTypes,
      primaryType: "EarlyShareEvidence",
      message: {
        jobId: evidence.jobId,
        memberIndex: evidence.memberIndex,
        shareHash: evidence.shareHash,
        memberSignatureHash,
      },
      signature: evidence.verifierSignature,
    });
    require(
      equalAddress(recoveredVerifier, scenario.constructor.verifier),
      `${scenario.mode}: verifier signature mismatch.`,
    );
    const digest = hashTypedData({
      domain,
      types: earlyShareEvidenceTypes,
      primaryType: "EarlyShareEvidence",
      message: {
        jobId: evidence.jobId,
        memberIndex: evidence.memberIndex,
        shareHash: evidence.shareHash,
        memberSignatureHash,
      },
    });
    require(
      digest.toLowerCase() === evidence.evidenceDigest.toLowerCase(),
      `${scenario.mode}: evidence digest mismatch.`,
    );
    require(
      await read<boolean>("usedEvidence", [digest]),
      `${scenario.mode}: evidence was not consumed.`,
    );
  }

  let earlySlashEvents = 0;
  let packageEvents = 0;
  let rewardWithdrawalEvents = 0;
  let treasuryWithdrawalEvents = 0;
  let eventMemberLoss = 0n;
  let eventCallerReward = 0n;
  let eventTreasuryAccrual = 0n;
  let packageMemberLoss = 0n;
  let packageCallerReward = 0n;
  let packageTreasuryAccrual = 0n;
  let withdrawnReward = 0n;
  let withdrawnTreasury = 0n;

  for (const transaction of scenario.transactions) {
    const receipt = receiptByHash.get(transaction.hash.toLowerCase());
    require(receipt !== undefined, `${transaction.label}: receipt missing.`);
    for (const log of receipt.logs) {
      if (!equalAddress(log.address, scenario.contractAddress)) continue;
      try {
        const decoded = decodeEventLog({
          abi: artifact.abi,
          data: log.data,
          topics: log.topics,
        });
        if (decoded.eventName === "EarlyShareSlashed") {
          const args = decoded.args as unknown as EarlySlashArgs;
          earlySlashEvents += 1;
          eventMemberLoss += args.memberLoss;
          eventCallerReward += args.callerReward;
          eventTreasuryAccrual += args.treasuryAccrual;
        } else if (decoded.eventName === "PackageSlashed") {
          const args = decoded.args as unknown as PackageSlashArgs;
          packageEvents += 1;
          require(
            Number(args.evidenceCount) === scenario.grouping[packageEvents - 1],
            `${scenario.mode}: package evidence count mismatch.`,
          );
          packageMemberLoss += args.totalMemberLoss;
          packageCallerReward += args.totalCallerReward;
          packageTreasuryAccrual += args.totalTreasuryAccrual;
        } else if (decoded.eventName === "RewardWithdrawn") {
          const args = decoded.args as unknown as WithdrawalArgs;
          rewardWithdrawalEvents += 1;
          require(
            equalAddress(args.recipient, scenario.constructor.owner),
            `${scenario.mode}: wrong reward recipient.`,
          );
          withdrawnReward += args.amount;
        } else if (decoded.eventName === "TreasuryWithdrawn") {
          const args = decoded.args as unknown as WithdrawalArgs;
          treasuryWithdrawalEvents += 1;
          require(
            equalAddress(args.recipient, scenario.constructor.owner),
            `${scenario.mode}: wrong treasury recipient.`,
          );
          withdrawnTreasury += args.amount;
        }
      } catch (error) {
        if (error instanceof Error && error.message.includes(`${scenario.mode}:`)) {
          throw error;
        }
        // Constructor and unrelated logs need not decode as target events.
      }
    }
  }

  require(earlySlashEvents === 4, `${scenario.mode}: wrong slash event count.`);
  require(
    packageEvents === scenario.grouping.length,
    `${scenario.mode}: wrong package event count.`,
  );
  require(
    rewardWithdrawalEvents === 1,
    `${scenario.mode}: missing reward withdrawal.`,
  );
  require(
    treasuryWithdrawalEvents === 1,
    `${scenario.mode}: missing treasury withdrawal.`,
  );
  require(eventMemberLoss === expectedLoss, `${scenario.mode}: event loss mismatch.`);
  require(
    eventCallerReward === expectedReward,
    `${scenario.mode}: event reward mismatch.`,
  );
  require(
    eventTreasuryAccrual === expectedTreasury,
    `${scenario.mode}: event treasury mismatch.`,
  );
  require(packageMemberLoss === expectedLoss, `${scenario.mode}: package loss mismatch.`);
  require(
    packageCallerReward === expectedReward,
    `${scenario.mode}: package reward mismatch.`,
  );
  require(
    packageTreasuryAccrual === expectedTreasury,
    `${scenario.mode}: package treasury mismatch.`,
  );
  require(withdrawnReward === expectedReward, `${scenario.mode}: withdrawn reward mismatch.`);
  require(
    withdrawnTreasury === expectedTreasury,
    `${scenario.mode}: withdrawn treasury mismatch.`,
  );

  require(
    BigInt(scenario.realizedCoveredBondLossWei) === expectedLoss,
    `${scenario.mode}: covered bond loss mismatch.`,
  );
  require(
    BigInt(scenario.callerRewardAccruedWei) === expectedReward,
    `${scenario.mode}: caller reward mismatch.`,
  );
  require(
    BigInt(scenario.treasuryAccruedBeforeWithdrawalWei) === expectedTreasury,
    `${scenario.mode}: pre-withdrawal treasury mismatch.`,
  );
  require(
    BigInt(scenario.treasuryAccruedAfterWithdrawalWei) === 0n,
    `${scenario.mode}: treasury was not withdrawn.`,
  );
  require(
    BigInt(scenario.remainingBondWei) === bond * 3n,
    `${scenario.mode}: remaining bond mismatch.`,
  );
  require(
    BigInt(scenario.postAttackCurrentCertificateWei) === 0n,
    `${scenario.mode}: exhausted certificate mismatch.`,
  );
  require(
    BigInt(scenario.callerRewardAfterWithdrawalWei) === 0n,
    `${scenario.mode}: reward was not withdrawn.`,
  );
  require(
    observedEnforcementGasCost === BigInt(scenario.enforcementGasCostWei),
    `${scenario.mode}: enforcement gas-cost mismatch.`,
  );
  require(
    expectedReward >= observedEnforcementGasCost,
    `${scenario.mode}: caller reward does not cover observed enforcement gas.`,
  );
  require(scenario.rewardCoversEnforcementGas, `${scenario.mode}: false coverage claim.`);
  require(
    BigInt(scenario.netCallerSurplusWei) ===
      expectedReward - observedEnforcementGasCost,
    `${scenario.mode}: net caller surplus mismatch.`,
  );
}

console.log("PHASE2_PUBLIC_RECEIPTS=PASS");
console.log("PHASE2_SOURCE_AND_DEPLOYMENT_INPUT=PASS");
console.log("PHASE2_MEMBER_AND_VERIFIER_SIGNATURES=PASS");
console.log("PHASE2_SEQUENTIAL_ATOMIC_REPEATED_EQUIVALENCE=PASS");
console.log("PHASE2_EXACT_REWARD_AND_TREASURY_WITHDRAWAL=PASS");
console.log("PHASE2_REWARD_GAS_COVERAGE=PASS");
console.log("PHASE2_SCOPE_GUARDS=PASS");
