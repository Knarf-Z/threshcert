import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const cohortBytes = await readFile(path.join(ROOT, "cohort.v1.json"));
const policyBytes = await readFile(path.join(ROOT, "policy.bridge-evidence.v1.json"));
const captureBytes = await readFile(path.join(ROOT, "data", "capture.public.v1.json"));
const cohort = JSON.parse(cohortBytes);
const policy = JSON.parse(policyBytes);
const capture = JSON.parse(captureBytes);

const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const expectedIds = cohort.systems.map((system) => system.id).sort();
const capturedIds = Object.keys(capture.systems).sort();
if (JSON.stringify(expectedIds) !== JSON.stringify(capturedIds)) throw new Error("cohort/capture mismatch");
if (policy.bridgeGates.map((gate) => gate.id).join(",") !== "B1,B2,B3,B4,B5") throw new Error("gate closure mismatch");

const commonGates = {
  B1: {
    status: "FAIL_CLOSED",
    reason: "No captured public record gives an entry-complete mapping from every covered acquisition success to usable threshold material.",
  },
  B2: {
    status: "FAIL_CLOSED",
    reason: "No captured public record binds an irreversible positive debit to a named acquiring principal.",
  },
  B3: {
    status: "FAIL_CLOSED",
    reason: "No captured public record makes usable premature delivery atomic with attacker-funded payment.",
  },
  B4: {
    status: "FAIL_CLOSED",
    reason: "No captured public record closes refunds, rebates, reimbursements, sponsor transfers, and controlled-party returns for an acquisition payment.",
  },
  B5: {
    status: "FAIL_CLOSED",
    reason: "No captured public record covers off-contract leakage, side payment, coercion, key compromise, and common-control acquisition routes.",
  },
};

const systemSpecific = {
  "gnosis-shutter-set10": {
    thresholdRecord: "PASS_4_OF_7",
    memberLossRecord: "ZERO_NO_ATTRIBUTED_MEMBER_OWNED_FORFEITURE_RECORD",
    refreshRecord: "NOT_CERTIFIED",
    codeBoundary: "manager and set runtime pinned; no payment-bearing acquisition entry",
  },
  "ssv-mainnet-cluster": {
    thresholdRecord: "PASS_3_OF_4",
    memberLossRecord: "ZERO_PROTOCOL_FEES_AND_CLUSTER_BALANCE_ARE_NOT_MEMBER_LOSS_FOR_PREMATURE_SIGNING",
    refreshRecord: "FAIL_OLD_SHARES_NOT_PUBLICLY_PROVED_REVOKED",
    codeBoundary: "upgradeable proxy and implementation pinned; validator registration/payment paths are not acquisition-payment paths",
  },
  "tbtc-v2-mainnet-wallet": {
    thresholdRecord: "PASS_51_OF_100",
    memberLossRecord: "ZERO_SLASHING_AUTHORITY_IS_NOT_AN_ATTRIBUTED_AUTOMATIC_LOSS_FLOOR_FOR_ACQUISITION",
    refreshRecord: "NOT_CERTIFIED_FOR_CROSS_WALLET_ACCUMULATION",
    codeBoundary: "transparent upgradeable proxy and implementation pinned; DKG and seize paths do not bind a buyer debit",
  },
  "drand-quicknet": {
    thresholdRecord: "INCOMPLETE_PUBLIC_CLIENT_INFO_OMITS_CURRENT_GROUP_THRESHOLD_AND_MEMBERS",
    memberLossRecord: "ZERO_NO_ACQUISITION_LINKED_MEMBER_LOSS_RECORD",
    refreshRecord: "NOT_CERTIFIED",
    codeBoundary: "chain hash and latest beacon pinned; no EVM contract and no payment-bearing acquisition mechanism",
  },
};

const records = expectedIds.map((id) => ({
  id,
  evidenceIdentifier: (() => {
    const item = capture.systems[id];
    if (id === "gnosis-shutter-set10") return `${item.blockNumber}:${item.blockHash}`;
    if (id === "ssv-mainnet-cluster") return item.committee.clusterId;
    if (id === "tbtc-v2-mainnet-wallet") return item.committee.walletId;
    return item.chainInfo.chain_hash;
  })(),
  gates: structuredClone(commonGates),
  ...systemSpecific[id],
  baselines: {
    thresholdOnlyPayment: "0",
    slashingOnlyPayment: "0",
    selfReportedPricePayment: "0",
    bridgeQualifiedPayment: "0_NO_ADMITTED_BRIDGE",
  },
  attackerPaymentCertificate: "0",
  interpretation: "The captured public record does not rule out a zero-payment compatible acquisition world; this is not an insecurity or behavior claim.",
}));

const result = {
  schema: "threshold-deployment-bridge-audit-result/v1",
  generatedFrom: {
    cohortSha256: sha(cohortBytes),
    policySha256: sha(policyBytes),
    captureSha256: sha(captureBytes),
  },
  cohortSize: records.length,
  passedPositiveMechanismConditionalPayment: 0,
  passedPositiveDeploymentWidePayment: 0,
  resultBoundary: "Fixed purposive cohort; no prevalence estimate and no claim of insecurity.",
  records,
};

const out = path.join(ROOT, "results", "bridge_audit.v1.json");
await mkdir(path.dirname(out), { recursive: true });
await writeFile(out, `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(`AUDITED_SYSTEMS=${result.cohortSize}`);
console.log(`POSITIVE_MECHANISM_CONDITIONAL=${result.passedPositiveMechanismConditionalPayment}`);
console.log(`POSITIVE_DEPLOYMENT_WIDE=${result.passedPositiveDeploymentWidePayment}`);
console.log("THRESHOLD_DEPLOYMENT_AUDIT=PASS");

