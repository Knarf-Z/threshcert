import { resolve } from "node:path";

import { network } from "hardhat";
import { getAddress, isHex, keccak256, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";

import { earlyShareTypes, evidenceDomain } from "../src/evidence.js";
import { artifactReference, readJson, requireEnv, writeJson } from "../src/io.js";
import { transactionRecord } from "../src/records.js";
import type { DeploymentFile, EvidenceFile, JobFile } from "../src/schema.js";

const connection = await network.create();
const { viem, networkName } = connection;
const publicClient = await viem.getPublicClient();
const [submitter] = await viem.getWalletClients();
if (submitter === undefined) throw new Error("network exposes no submitter wallet");

const deploymentPath = resolve(
  process.env.DEPLOYMENT_FILE?.trim() ?? `results/deployment-${networkName}.json`,
);
const jobPath = resolve(
  process.env.JOB_FILE?.trim() ?? `results/job-${networkName}.json`,
);
const evidencePath = resolve(requireEnv("EVIDENCE_FILE"));
const deployment = await readJson<DeploymentFile>(deploymentPath);
const job = await readJson<JobFile>(jobPath);
const evidence = await readJson<EvidenceFile>(evidencePath);
const chainId = await publicClient.getChainId();

if (deployment.chainId !== chainId || job.chainId !== chainId) {
  throw new Error("chain ID mismatch among network, deployment, and job");
}
if (job.contract !== deployment.contract) throw new Error("job contract mismatch");
if (job.identityHash !== evidence.identityHash) throw new Error("identity hash mismatch");
if (job.eon !== evidence.eon) throw new Error("eon mismatch");
if (!evidence.aggregateKeyValid || !evidence.reconstructionMatchesStoredKey) {
  throw new Error("aggregate Shutter key was not independently validated");
}

const requested = Number(process.env.MEMBER_INDEX?.trim() ?? "0");
const share = evidence.shares.find((candidate) => candidate.memberIndex === requested);
if (!share) throw new Error(`evidence has no share for member ${requested}`);
if (!share.shareValid || !share.nativeSignatureValid) {
  throw new Error("refusing to attest an unvalidated share or native signature");
}
if (!isHex(share.share) || !isHex(share.nativeSignature)) {
  throw new Error("share and native signature must be hex encoded");
}
const configured = deployment.keypers.find((keyper) => keyper.index === requested);
if (!configured || getAddress(configured.address) !== getAddress(share.keyperAddress)) {
  throw new Error("evidence Keyper address does not match the bonded committee");
}

const verifierKey = requireEnv("EVIDENCE_VERIFIER_PRIVATE_KEY") as Hex;
if (!/^0x[0-9a-fA-F]{64}$/.test(verifierKey)) {
  throw new Error("EVIDENCE_VERIFIER_PRIVATE_KEY must be a 32-byte 0x-prefixed key");
}
const verifier = privateKeyToAccount(verifierKey);
if (getAddress(verifier.address) !== getAddress(deployment.verifier)) {
  throw new Error("verifier private key does not match the deployment record");
}

const message = {
  jobId: job.jobId,
  memberIndex: requested,
  shareHash: share.shareHash ?? keccak256(share.share),
  memberSignatureHash: share.nativeSignatureHash ?? keccak256(share.nativeSignature),
} as const;
const verifierSignature = await verifier.signTypedData({
  domain: evidenceDomain(chainId, deployment.contract),
  types: earlyShareTypes,
  primaryType: "EarlyShareEvidence",
  message,
});

const contract = await viem.getContractAt("BondedKeyperSlasher", deployment.contract);
const certificateBefore = await contract.read.currentCertificate();
const hash = await contract.write.slashEarlyShare(
  [
    message.jobId,
    message.memberIndex,
    message.shareHash,
    message.memberSignatureHash,
    verifierSignature,
  ],
  { account: submitter.account },
);
const receipt = await publicClient.waitForTransactionReceipt({ hash });
const certificateAfter = await contract.read.currentCertificate();
const block = await publicClient.getBlock({ blockNumber: receipt.blockNumber });

const result = {
  schema: "fc-slashing-result-v1",
  generatedAt: new Date().toISOString(),
  deploymentFile: artifactReference(deploymentPath),
  jobFile: artifactReference(jobPath),
  evidenceFile: artifactReference(evidencePath),
  chainId,
  contract: deployment.contract,
  jobId: job.jobId,
  memberIndex: requested,
  keyperAddress: share.keyperAddress,
  shareHash: message.shareHash,
  memberSignatureHash: message.memberSignatureHash,
  verifier: verifier.address,
  observedAt: block.timestamp.toString(),
  releaseTime: job.releaseTime,
  prematureBySeconds: (BigInt(job.releaseTime) - block.timestamp).toString(),
  certificateBeforeWei: certificateBefore.toString(),
  certificateAfterWei: certificateAfter.toString(),
  transaction: transactionRecord(receipt),
};
const output = process.env.SLASHING_OUTPUT?.trim()
  ?? `results/slashing-${networkName}.json`;
console.log(`slashing_tx=${hash}`);
console.log(`certificate_before_wei=${certificateBefore}`);
console.log(`certificate_after_wei=${certificateAfter}`);
console.log(`slashing_record=${await writeJson(resolve(output), result)}`);
