import { resolve } from "node:path";

import { network } from "hardhat";
import { keccak256, parseEther, stringToHex } from "viem";

import { earlyShareTypes, evidenceDomain } from "../src/evidence.js";
import { writeJson } from "../src/io.js";
import { transactionRecord } from "../src/records.js";

const { viem } = await network.create();
const publicClient = await viem.getPublicClient();
const wallets = await viem.getWalletClients();
const [owner, verifier, treasury, submitter, ...memberWallets] = wallets;
const members = memberWallets.slice(0, 7);
const bond = parseEther("2");
const chainId = await publicClient.getChainId();

const { contract, deploymentTransaction } = await viem.sendDeploymentTransaction(
  "BondedKeyperSlasher",
  [owner.account.address, verifier.account.address, treasury.account.address],
  { client: { wallet: owner, public: publicClient } },
);
const deployReceipt = await publicClient.waitForTransactionReceipt({
  hash: deploymentTransaction.hash,
});
const registrations = [];
for (let index = 0; index < 7; index += 1) {
  const hash = await contract.write.registerMember(
    [index, members[index].account.address],
    { account: owner.account, value: bond },
  );
  registrations.push({ memberIndex: index, ...transactionRecord(
    await publicClient.waitForTransactionReceipt({ hash }),
  ) });
}
const freezeHash = await contract.write.freezeCommittee({ account: owner.account });
const freezeReceipt = await publicClient.waitForTransactionReceipt({ hash: freezeHash });
const certificateBefore = await contract.read.currentCertificate();

const block = await publicClient.getBlock();
const releaseTime = block.timestamp + 3_600n;
const identityHash = keccak256(stringToHex("fc-local-contract-harness"));
const openHash = await contract.write.openRelease([1n, identityHash, releaseTime], {
  account: owner.account,
});
const openReceipt = await publicClient.waitForTransactionReceipt({ hash: openHash });
const nonce = await contract.read.jobCount();
const jobId = await contract.read.computeJobId([1n, identityHash, releaseTime, nonce]);
const message = {
  jobId,
  memberIndex: 0,
  shareHash: keccak256(stringToHex("synthetic-share-contract-harness-only")),
  memberSignatureHash: keccak256(stringToHex("synthetic-native-signature-contract-harness-only")),
} as const;
const signature = await verifier.signTypedData({
  account: verifier.account,
  domain: evidenceDomain(chainId, contract.address),
  types: earlyShareTypes,
  primaryType: "EarlyShareEvidence",
  message,
});
const slashHash = await contract.write.slashEarlyShare(
  [jobId, 0, message.shareHash, message.memberSignatureHash, signature],
  { account: submitter.account },
);
const slashReceipt = await publicClient.waitForTransactionReceipt({ hash: slashHash });
const certificateAfter = await contract.read.currentCertificate();

const result = {
  schema: "fc-local-contract-e2e-v1",
  generatedAt: new Date().toISOString(),
  evidenceMode: "synthetic-contract-harness-only",
  warning: "This record tests contract wiring and is not Rolling Shutter deployment evidence.",
  chainId,
  contract: contract.address,
  committeeSize: 7,
  threshold: 4,
  bondWeiPerMember: bond.toString(),
  certificateBeforeWei: certificateBefore.toString(),
  certificateAfterWei: certificateAfter.toString(),
  transactions: {
    deploy: transactionRecord(deployReceipt),
    registrations,
    freeze: transactionRecord(freezeReceipt),
    openRelease: transactionRecord(openReceipt),
    slash: transactionRecord(slashReceipt),
  },
};
const output = process.env.LOCAL_E2E_OUTPUT?.trim() ?? "results/local-contract-e2e.json";
console.log(`local_contract_e2e=${await writeJson(resolve(output), result)}`);
console.log(`certificate_before_wei=${certificateBefore}`);
console.log(`certificate_after_wei=${certificateAfter}`);
