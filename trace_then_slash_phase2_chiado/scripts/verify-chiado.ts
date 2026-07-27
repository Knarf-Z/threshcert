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
  blockNumber: string;
  blockHash: Hex;
  status: string;
  gasUsed: string;
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
  realizedMemberLossWei: string;
  callerRewardAccruedWei: string;
  callerRewardAfterWithdrawalWei: string;
  treasuryAccruedWei: string;
  remainingBondWei: string;
  postAttackCurrentCertificateWei: string;
  slashTransactionHashes: Hex[];
  rewardWithdrawalTransactionHash: Hex;
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

function require(condition: boolean, message: string): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

const root = resolve(import.meta.dirname, "..");
const rpcUrl =
  process.env.CHIADO_VERIFY_RPC_URL ?? process.env.CHIADO_RPC_URL;
if (rpcUrl === undefined || rpcUrl.length === 0) {
  throw new Error("Set CHIADO_VERIFY_RPC_URL to an independent Chiado RPC.");
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
  result.schema === "fc-trace-then-slash-phase2-chiado-v1",
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
const expectedTreasury = expectedLoss - rewardPerSlash * 4n;
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
    !scenario.memberSignerAddresses
      .map((item) => item.toLowerCase())
      .includes(scenario.submitter.toLowerCase()),
    `${scenario.mode}: submitter is a registered member.`,
  );

  for (const transaction of scenario.transactions) {
    const receipt = await client.getTransactionReceipt({
      hash: transaction.hash,
    });
    require(receipt.status === "success", `${transaction.label}: failed.`);
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
      `${transaction.label}: gas mismatch.`,
    );
  }

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
    `${scenario.mode}: deployment input does not match local source artifact.`,
  );

  const code = await client.getCode({ address: scenario.contractAddress });
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
    }) as Promise<T>;

  require(
    (await read<Address>("owner")).toLowerCase() ===
      scenario.constructor.owner.toLowerCase(),
    `${scenario.mode}: owner mismatch.`,
  );
  require(
    (await read<Address>("verifier")).toLowerCase() ===
      scenario.constructor.verifier.toLowerCase(),
    `${scenario.mode}: verifier mismatch.`,
  );
  require(
    (await read<Address>("treasury")).toLowerCase() ===
      scenario.constructor.treasury.toLowerCase(),
    `${scenario.mode}: treasury mismatch.`,
  );
  require(
    await read<boolean>("committeeFrozen"),
    `${scenario.mode}: committee is not frozen.`,
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
      BigInt(scenario.treasuryAccruedWei),
    `${scenario.mode}: treasury mismatch.`,
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
      member[0].toLowerCase() ===
        scenario.memberSignerAddresses[index].toLowerCase(),
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
      recoveredMember.toLowerCase() ===
        scenario.memberSignerAddresses[evidence.memberIndex].toLowerCase(),
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
      recoveredVerifier.toLowerCase() ===
        scenario.constructor.verifier.toLowerCase(),
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
  let withdrawalEvents = 0;
  for (const transaction of scenario.transactions) {
    const receipt = await client.getTransactionReceipt({
      hash: transaction.hash,
    });
    for (const log of receipt.logs) {
      if (log.address.toLowerCase() !== scenario.contractAddress.toLowerCase()) {
        continue;
      }
      try {
        const decoded = decodeEventLog({
          abi: artifact.abi,
          data: log.data,
          topics: log.topics,
        });
        if (decoded.eventName === "EarlyShareSlashed") earlySlashEvents += 1;
        if (decoded.eventName === "PackageSlashed") packageEvents += 1;
        if (decoded.eventName === "RewardWithdrawn") withdrawalEvents += 1;
      } catch {
        // Constructor and unrelated logs need not decode as target events.
      }
    }
  }
  require(earlySlashEvents === 4, `${scenario.mode}: wrong slash event count.`);
  require(
    packageEvents === scenario.grouping.length,
    `${scenario.mode}: wrong package event count.`,
  );
  require(withdrawalEvents === 1, `${scenario.mode}: missing reward withdrawal.`);

  require(
    BigInt(scenario.realizedMemberLossWei) === expectedLoss,
    `${scenario.mode}: loss mismatch.`,
  );
  require(
    BigInt(scenario.callerRewardAccruedWei) === rewardPerSlash * 4n,
    `${scenario.mode}: caller reward mismatch.`,
  );
  require(
    BigInt(scenario.treasuryAccruedWei) === expectedTreasury,
    `${scenario.mode}: treasury mismatch.`,
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
}

console.log("PHASE2_PUBLIC_RECEIPTS=PASS");
console.log("PHASE2_SOURCE_AND_DEPLOYMENT_INPUT=PASS");
console.log("PHASE2_MEMBER_AND_VERIFIER_SIGNATURES=PASS");
console.log("PHASE2_SEQUENTIAL_ATOMIC_REPEATED_EQUIVALENCE=PASS");
console.log("PHASE2_EXACT_REWARD_WITHDRAWAL=PASS");
console.log("PHASE2_SCOPE_GUARDS=PASS");
