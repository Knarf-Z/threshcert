import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const temp = await mkdtemp(path.join(os.tmpdir(), "third-party-screen-v2-"));
const digest = (hex) => createHash("sha256").update(Buffer.from(hex.slice(2), "hex")).digest("hex");
const zero = `0x${"00".repeat(32)}`;
const evidence = Object.fromEntries([
  "entryClosure",
  "payerSeparation",
  "paymentPreservation",
  "backwardRealization",
  "terminalEquivalence",
  "offsetClosure",
].map((name, index) => [name, { status: "PASS", evidenceSha256: `${index + 1}`.repeat(64) }]));

const baseRuntime = "0x60006000";
const baseRecord = {
  schema: "third-party-runtime-record/v1",
  subject: { address: `0x${"12".repeat(20)}` },
  chain: { chainId: 1, blockNumber: "1", blockHash: `0x${"ab".repeat(32)}` },
  deployment: { to: null, input: "0x6000", receiptStatus: "success", contractAddress: `0x${"12".repeat(20)}` },
  runtime: { code: baseRuntime, sha256: digest(baseRuntime) },
  proxySlots: { implementation: zero, admin: zero, beacon: zero },
  semanticCertificate: evidence,
};
const baseArtifact = {
  abi: [],
  bytecode: { object: "0x6000" },
  deployedBytecode: { object: baseRuntime, immutableReferences: {}, linkReferences: {} },
};
const policy = {
  id: "synthetic-direct-closed/v2",
  requiredLayers: ["provenance", "identity", "template", "controlFlow", "abi", "semanticIncidence"],
  forbiddenOpcodes: ["callcode", "delegatecall", "create", "create2", "selfdestruct"],
  requireZeroProxySlots: true,
  forbidFallbackOrReceive: true,
  allowedMutatingSignatures: [],
  requiredSemanticChecks: Object.keys(evidence),
};

async function runCase(name, mutate = () => {}) {
  const record = structuredClone(baseRecord);
  const artifact = structuredClone(baseArtifact);
  const localPolicy = structuredClone(policy);
  mutate(record, artifact, localPolicy);
  const recordPath = path.join(temp, `${name}.record.json`);
  const artifactPath = path.join(temp, `${name}.artifact.json`);
  const policyPath = path.join(temp, `${name}.policy.json`);
  const resultPath = path.join(temp, `${name}.result.json`);
  await Promise.all([
    writeFile(recordPath, JSON.stringify(record)),
    writeFile(artifactPath, JSON.stringify(artifact)),
    writeFile(policyPath, JSON.stringify(localPolicy)),
  ]);
  const child = spawnSync(process.execPath, [
    path.join(root, "screen_contract_v2.mjs"),
    "--record", recordPath,
    "--artifact", artifactPath,
    "--policy", policyPath,
    "--out", resultPath,
  ], { encoding: "utf8" });
  assert.equal(child.status, 0, `${name}: ${child.stderr}`);
  return JSON.parse(await readFile(resultPath, "utf8"));
}

try {
  const baseline = await runCase("baseline");
  assert.equal(baseline.commonStaticScreen, "PASS");
  assert.equal(baseline.closedContractAdmission, "PASS");

  const cases = [
    ["bad-chain-pin", (record) => { record.chain.blockHash = "0x01"; }],
    ["bad-runtime-hash", (record) => { record.runtime.sha256 = "00".repeat(32); }],
    ["template-mismatch", (_record, artifact) => { artifact.deployedBytecode.object = "0x60016000"; }],
    ["nonzero-proxy-slot", (record) => { record.proxySlots.implementation = `0x${"00".repeat(31)}01`; }],
    ["delegatecall", (record, artifact) => {
      record.runtime.code = "0xf4";
      record.runtime.sha256 = digest(record.runtime.code);
      artifact.deployedBytecode.object = record.runtime.code;
    }],
    ["invalid-semantic-digest", (record) => { record.semanticCertificate.entryClosure.evidenceSha256 = "not-a-digest"; }],
    ["fallback-added", (_record, artifact) => { artifact.abi = [{ type: "fallback", stateMutability: "payable" }]; }],
    ["noncreation-transaction", (record) => { record.deployment.to = `0x${"34".repeat(20)}`; }],
  ];
  for (const [name, mutate] of cases) {
    const result = await runCase(name, mutate);
    assert.equal(result.closedContractAdmission, "FAIL_CLOSED", name);
  }
  console.log(`PASS: baseline admission plus ${cases.length} fail-closed tamper cases`);
} finally {
  await rm(temp, { recursive: true, force: true });
}
