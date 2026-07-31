import { createHash } from "node:crypto";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const CHECKER = path.join(ROOT, "verify_deployment_admission.mjs");
const CANONICAL = path.join(ROOT, "results", "deployment_admission_local.json");
const original = JSON.parse(await readFile(CANONICAL, "utf8"));
const clone = () => structuredClone(original);
const cases = [
  ["creation-input", (x) => { x.deployment.input = `${x.deployment.input.slice(0, -2)}00`; }],
  ["runtime-template", (x) => { x.runtime.code = `${x.runtime.code.slice(0, 20)}ff${x.runtime.code.slice(22)}`; }],
  ["constructor-controller", (x) => { x.constructor.controller = "0x0000000000000000000000000000000000000001"; }],
  ["nonfresh-state", (x) => { x.observationsAtDeploymentBlock.configured = true; }],
  ["nonzero-acquirer", (x) => { x.observationsAtDeploymentBlock.acquirer = "0x0000000000000000000000000000000000000001"; }],
  ["controller-member-role", (x) => { x.constructor.members[0] = x.constructor.controller; }],
  ["initial-share-owner", (x) => { x.observationsAtDeploymentBlock.shareOwners[0] = "0x0000000000000000000000000000000000000001"; }],
  ["receipt-block", (x) => { x.deployment.receiptBlockHash = `0x${"00".repeat(32)}`; }],
  ["transaction-order", (x) => { x.chain.transactionHashes.push(`0x${"11".repeat(32)}`); }],
  ["immutable-reference", (x) => { x.runtime.immutableReferences = {}; }],
];
const directory = await mkdtemp(path.join(tmpdir(), "ope-admission-negative-"));
for (const [name, mutate] of cases) {
  const record = clone();
  mutate(record);
  const recordPath = path.join(directory, `${name}.json`);
  const certificatePath = path.join(directory, `${name}-certificate.json`);
  await writeFile(recordPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  const run = spawnSync(process.execPath, [CHECKER, "--record", recordPath, "--certificate", certificatePath], { encoding: "utf8", windowsHide: true });
  if (run.status === 0) throw new Error(`tamper case was accepted: ${name}`);
  console.log(`DEPLOYMENT_ADMISSION_REJECT_${name.toUpperCase().replaceAll("-", "_")}=PASS`);
}
const result = {
  schema: "overlapping-pool-deployment-admission-negative/v1",
  status: "PASS",
  canonicalRecordSha256: createHash("sha256").update(await readFile(CANONICAL)).digest("hex"),
  checkerSha256: createHash("sha256").update(await readFile(CHECKER)).digest("hex"),
  rejectedTamperCases: cases.map(([name]) => name),
  totalRejected: cases.length,
};
await writeFile(path.join(ROOT, "results", "deployment_admission_negative.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(`DEPLOYMENT_ADMISSION_NEGATIVE_TAMPER_CASES=${cases.length}_PASS`);