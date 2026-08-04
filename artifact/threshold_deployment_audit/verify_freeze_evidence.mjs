import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const expectedCommit = "bd58e0ec733c43d215110349f91cc31ec303b0ab";
const expectedTree = "c452714e7b57fcfd9efc8e9c12100271c73da1ee";
const evidence = path.join(root, "freeze_evidence");

const raw = await readFile(path.join(evidence, "commit.bd58e0e.raw"));
const header = Buffer.from(`commit ${raw.length}\0`, "ascii");
const actualCommit = createHash("sha1").update(header).update(raw).digest("hex");
if (actualCommit !== expectedCommit) {
  throw new Error(`freeze commit object mismatch: expected ${expectedCommit}, actual ${actualCommit}`);
}
const rawText = raw.toString("utf8");
if (!rawText.startsWith(`tree ${expectedTree}\n`)) {
  throw new Error(`freeze tree mismatch: expected ${expectedTree}`);
}

const bundle = await readFile(path.join(evidence, "frozen_plan_bd58e0e.bundle"));
const bundleHeader = bundle.subarray(0, Math.min(bundle.length, 4096)).toString("utf8");
if (!bundleHeader.startsWith("# v2 git bundle\n")) throw new Error("freeze bundle header missing");
if (!bundleHeader.includes(`${expectedCommit} refs/heads/artifact-freeze-plan-v46\n`)) {
  throw new Error(`freeze bundle does not advertise ${expectedCommit}`);
}

console.log(`FREEZE_COMMIT=${expectedCommit}`);
console.log(`FREEZE_TREE=${expectedTree}`);
console.log("FREEZE_EVIDENCE=PASS");
