import { resolve } from "node:path";

import { network } from "hardhat";
import { isHex, keccak256, stringToHex, type Hex } from "viem";

import { artifactReference, readJson, writeJson } from "../src/io.js";
import { transactionRecord } from "../src/records.js";
import type { EvidenceFile, JobFile, RewardedDeploymentFile } from "../src/schema.js";

/// Opens a release job against the parallel, additive
/// `BondedKeyperSlasherRewarded` contract -- see deploy-rewarded.ts and
/// BondedKeyperSlasherRewarded.sol for why this is a new script rather
/// than an edit of open-release.ts / BondedKeyperSlasher.sol.

const connection = await network.create();
const { viem, networkName } = connection;
const publicClient = await viem.getPublicClient();
const [ownerWallet] = await viem.getWalletClients();
if (ownerWallet === undefined) throw new Error("network exposes no transaction wallet");

const deploymentPath = resolve(
  process.env.DEPLOYMENT_FILE?.trim() ?? `results/deployment-${networkName}-rewarded.json`,
);
const deployment = await readJson<RewardedDeploymentFile>(deploymentPath);
const chainId = await publicClient.getChainId();
if (deployment.chainId !== chainId) throw new Error("deployment file chain ID mismatch");

let identityPreimage: Hex;
let eon: bigint;
const evidencePath = process.env.EVIDENCE_FILE?.trim();
if (evidencePath) {
  const evidence = await readJson<EvidenceFile>(evidencePath);
  if (evidence.schema !== "fc-shutter-evidence-v1") throw new Error("unknown evidence schema");
  identityPreimage = evidence.identityPreimage;
  eon = BigInt(evidence.eon);
} else {
  const raw = process.env.IDENTITY_PREIMAGE_HEX?.trim();
  identityPreimage = raw && isHex(raw) ? raw : stringToHex("fc-real-deployment-pilot-rewarded");
  eon = BigInt(process.env.EON?.trim() ?? "1");
}
const identityHash = keccak256(identityPreimage);
const delay = BigInt(process.env.RELEASE_DELAY_SECONDS?.trim() ?? "1800");
if (delay < 120n) throw new Error("RELEASE_DELAY_SECONDS must be at least 120");
const latest = await publicClient.getBlock();
const releaseTime = latest.timestamp + delay;

const contract = await viem.getContractAt("BondedKeyperSlasherRewarded", deployment.contract);
const hash = await contract.write.openRelease(
  [eon, identityHash, releaseTime],
  { account: ownerWallet.account },
);
const receipt = await publicClient.waitForTransactionReceipt({ hash });
const nonce = await contract.read.jobCount();
const jobId = await contract.read.computeJobId([eon, identityHash, releaseTime, nonce]);

const result: JobFile = {
  schema: "fc-release-job-v1",
  generatedAt: new Date().toISOString(),
  deploymentFile: artifactReference(deploymentPath),
  chainId,
  contract: deployment.contract,
  jobId,
  eon: eon.toString(),
  identityPreimage,
  identityHash,
  releaseTime: releaseTime.toString(),
  nonce: nonce.toString(),
  transaction: transactionRecord(receipt),
};
const output = process.env.JOB_OUTPUT?.trim() ?? `results/job-${networkName}-rewarded.json`;
console.log(`job_id=${jobId}`);
console.log(`release_time=${releaseTime}`);
console.log(`job_record=${await writeJson(resolve(output), result)}`);
