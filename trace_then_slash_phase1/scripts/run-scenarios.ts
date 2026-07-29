import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { network } from "hardhat";
import {
  keccak256,
  parseEther,
  stringToHex,
  type Hex,
} from "viem";

import {
  signArtifact,
  signVerifierEvidence,
  type EarlyShareArtifact,
} from "../src/evidence.js";

const BOND = parseEther("2");
const CALLER_REWARD = parseEther("0.1");
const TARGET_MEMBERS = [0, 1, 2, 3] as const;

type Mode = "sequential" | "atomic_package" | "repeated_packages";
type SignedEvidence = EarlyShareArtifact & {
  memberSignature: Hex;
  verifierSignature: Hex;
};

async function runScenario(mode: Mode) {
  const connection = await network.create();
  const { viem } = connection;
  const publicClient = await viem.getPublicClient();
  const wallets = await viem.getWalletClients();
  const [owner, verifier, treasury, submitter, ...memberWallets] = wallets;
  const members = memberWallets.slice(0, 7);

  const contract = await viem.deployContract("TraceThenSlash", [
    owner.account.address,
    verifier.account.address,
    treasury.account.address,
    CALLER_REWARD,
  ]);
  for (let index = 0; index < 7; index += 1) {
    await contract.write.registerMember(
      [index, members[index].account.address],
      { account: owner.account, value: BOND },
    );
  }
  await contract.write.freezeCommittee({ account: owner.account });

  const initialCertificate = await contract.read.frozenThresholdBondFloor();
  const initialTotalBond = await contract.read.totalBond();
  const releaseTime = 4_102_448_400n;
  const identityHash = keccak256(stringToHex(`rq2-phase1-${mode}`));
  await contract.write.openRelease([1n, identityHash, releaseTime], {
    account: owner.account,
  });
  const nonce = await contract.read.jobCount();
  const jobId = await contract.read.computeJobId([
    1n,
    identityHash,
    releaseTime,
    nonce,
  ]);
  const chainId = await publicClient.getChainId();

  const evidence: SignedEvidence[] = [];
  for (const memberIndex of TARGET_MEMBERS) {
    const artifact: EarlyShareArtifact = {
      jobId,
      memberIndex,
      shareHash: keccak256(
        stringToHex(`covered-early-share-${mode}-${memberIndex}`),
      ),
    };
    const memberSignature = await signArtifact(
      members[memberIndex],
      chainId,
      contract.address,
      artifact,
    );
    const verifierSignature = await signVerifierEvidence(
      verifier,
      chainId,
      contract.address,
      artifact,
      memberSignature,
    );
    evidence.push({ ...artifact, memberSignature, verifierSignature });
  }

  const packageArgs = (slice: typeof evidence) =>
    [
      slice.map((item) => item.jobId),
      slice.map((item) => item.memberIndex),
      slice.map((item) => item.shareHash),
      slice.map((item) => item.memberSignature),
      slice.map((item) => item.verifierSignature),
    ] as const;

  const hashes: Hex[] = [];
  if (mode === "sequential") {
    for (const item of evidence) {
      hashes.push(
        await contract.write.slashEarlyShare(
          [
            item.jobId,
            item.memberIndex,
            item.shareHash,
            item.memberSignature,
            item.verifierSignature,
          ],
          { account: submitter.account },
        ),
      );
    }
  } else if (mode === "atomic_package") {
    hashes.push(
      await contract.write.slashPackage(packageArgs(evidence), {
        account: submitter.account,
      }),
    );
  } else {
    hashes.push(
      await contract.write.slashPackage(packageArgs(evidence.slice(0, 2)), {
        account: submitter.account,
      }),
    );
    hashes.push(
      await contract.write.slashPackage(packageArgs(evidence.slice(2, 4)), {
        account: submitter.account,
      }),
    );
  }

  const receipts = [];
  for (const hash of hashes) {
    const receipt = await publicClient.waitForTransactionReceipt({ hash });
    receipts.push({
      hash,
      blockNumber: receipt.blockNumber.toString(),
      status: receipt.status,
      gasUsed: receipt.gasUsed.toString(),
    });
  }

  const postAttackCertificate = await contract.read.currentCertificate();
  const remainingBond = await contract.read.totalBond();
  const callerReward = await contract.read.claimableRewards([
    submitter.account.address,
  ]);
  const treasuryAccrual = await contract.read.treasuryAccrued();
  const realizedMemberLoss = initialTotalBond - remainingBond;

  return {
    mode,
    chainId,
    contract: contract.address,
    jobId,
    releaseTime: releaseTime.toString(),
    grouping:
      mode === "sequential" ? [1, 1, 1, 1] :
      mode === "atomic_package" ? [4] :
      [2, 2],
    slashedMemberIndices: [...TARGET_MEMBERS],
    initialTotalBondWei: initialTotalBond.toString(),
    preAttackThresholdBondFloorWei: initialCertificate.toString(),
    realizedMemberLossWei: realizedMemberLoss.toString(),
    callerRewardAccruedWei: callerReward.toString(),
    treasuryAccruedWei: treasuryAccrual.toString(),
    remainingBondWei: remainingBond.toString(),
    postAttackCurrentCertificateWei: postAttackCertificate.toString(),
    transactions: receipts,
  };
}

const root = resolve(import.meta.dirname, "..");
const contractSource = await readFile(
  resolve(root, "contracts/TraceThenSlash.sol"),
);
const scenarios = [];
for (const mode of [
  "sequential",
  "atomic_package",
  "repeated_packages",
] as const) {
  scenarios.push(await runScenario(mode));
}

const result = {
  schema: "fc-trace-then-slash-phase1-v1",
  fixtureGenesis: "2026-01-01T00:00:00.000Z",
  rq: "RQ2",
  environment: {
    execution: "Hardhat ephemeral EVM",
    hostModel: "single host, seven distinct accountability keys",
    independentOperators: false,
    productionDeployment: false,
  },
  committee: {
    size: 7,
    threshold: 4,
    bondWeiPerMember: BOND.toString(),
    callerRewardWeiPerSlash: CALLER_REWARD.toString(),
  },
  coverage: {
    mechanismClass:
      "member-signed public early-share artifact plus verifier attestation",
    packageSizeParameterB: "not used",
    acceptedAtomicPackageSizes: [1, 2, 3, 4, 5, 6, 7],
    repeatedPackages: true,
    silentOffProtocolTransfers: false,
  },
  certificate: {
    status: "POSITIVE_SCOPED",
    lowerBoundWei: parseEther("8").toString(),
    unit: "bonded ETH",
    statement:
      "Under the stated artifact, verifier, timely-submission, and chain-liveness assumptions, any covered 4-of-7 early reconstruction realizes at least the sum of the four smallest frozen bonds.",
  },
  contractSourceSha256: createHash("sha256").update(contractSource).digest("hex"),
  scenarios,
};

await mkdir(resolve(root, "results"), { recursive: true });
const output = resolve(root, "results/phase1_scenarios.json");
await writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(`phase1_results=${output}`);
for (const scenario of scenarios) {
  console.log(
    `${scenario.mode}: loss_wei=${scenario.realizedMemberLossWei} reward_wei=${scenario.callerRewardAccruedWei}`,
  );
}
