import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const read = async (relative) => {
  const bytes = await readFile(path.join(ROOT, relative));
  return { bytes, value: JSON.parse(bytes) };
};

const cohort = await read("cohort.v1.json");
const policy = await read("policy.bridge-evidence.v1.json");
const capture = await read("data/capture.public.v1.json");
const result = await read("results/bridge_audit.v1.json");
const ids = cohort.value.systems.map((x) => x.id).sort();
if (ids.length !== 4) throw new Error("unexpected cohort size");
if (JSON.stringify(ids) !== JSON.stringify(Object.keys(capture.value.systems).sort())) throw new Error("capture mismatch");
if (result.value.generatedFrom.cohortSha256 !== sha(cohort.bytes)) throw new Error("cohort hash mismatch");
if (result.value.generatedFrom.policySha256 !== sha(policy.bytes)) throw new Error("policy hash mismatch");
if (result.value.generatedFrom.captureSha256 !== sha(capture.bytes)) throw new Error("capture hash mismatch");
if (result.value.cohortSize !== 4 || result.value.records.length !== 4) throw new Error("result size mismatch");
if (result.value.passedPositiveMechanismConditionalPayment !== 0) throw new Error("unexpected mechanism pass");
if (result.value.passedPositiveDeploymentWidePayment !== 0) throw new Error("unexpected deployment pass");
for (const record of result.value.records) {
  if (record.attackerPaymentCertificate !== "0") throw new Error(`${record.id}: nonzero certificate`);
  for (const gate of ["B1", "B2", "B3", "B4", "B5"]) {
    if (record.gates[gate]?.status !== "FAIL_CLOSED") throw new Error(`${record.id}: bad ${gate}`);
  }
  if (record.baselines.thresholdOnlyPayment !== "0") throw new Error(`${record.id}: threshold baseline`);
  if (record.baselines.slashingOnlyPayment !== "0") throw new Error(`${record.id}: slashing baseline`);
  if (record.baselines.selfReportedPricePayment !== "0") throw new Error(`${record.id}: report baseline`);
}
const ssv = capture.value.systems["ssv-mainnet-cluster"];
if (ssv.committee.operators.length !== 4 || ssv.committee.threshold !== 3) throw new Error("SSV committee mismatch");
const tbtc = capture.value.systems["tbtc-v2-mainnet-wallet"];
if (tbtc.committee.members.length !== 100 || tbtc.committee.threshold !== 51) throw new Error("tBTC committee mismatch");
const shutter = capture.value.systems["gnosis-shutter-set10"];
if (shutter.committee.members.length !== 7 || shutter.committee.threshold !== 4) throw new Error("Shutter committee mismatch");
const drand = capture.value.systems["drand-quicknet"];
if (drand.committee.status !== "NOT_EXPOSED_BY_OFFICIAL_PUBLIC_CLIENT_INFO_ENDPOINT") throw new Error("drand disclosure status mismatch");
console.log("THRESHOLD_DEPLOYMENT_AUDIT_OFFLINE=PASS");

