import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const [source, mocks, test, artifactBytes, certificateBytes, transcript] = await Promise.all([
  readFile(path.join(ROOT, "contracts", "PrefundedThresholdExchange.sol")),
  readFile(path.join(ROOT, "contracts", "test", "MockThresholdBridgeDependencies.sol")),
  readFile(path.join(ROOT, "test", "PrefundedThresholdExchange.ts")),
  readFile(path.join(ROOT, "artifacts", "contracts", "PrefundedThresholdExchange.sol", "PrefundedThresholdExchange.json")),
  readFile(path.join(ROOT, "results", "prefunded_threshold_exchange.json")),
  readFile(path.join(ROOT, "results", "prefunded_threshold_exchange.log")),
]);
const artifact = JSON.parse(artifactBytes);
const certificate = JSON.parse(certificateBytes);
if (certificate.schema !== "prefunded-threshold-exchange-test/v1" || certificate.status !== "PASS") throw new Error("bad certificate");
if (certificate.inputs.sourceSha256 !== sha(source)) throw new Error("source hash mismatch");
if (certificate.inputs.mockDependenciesSha256 !== sha(mocks)) throw new Error("mock hash mismatch");
if (certificate.inputs.testSha256 !== sha(test)) throw new Error("test hash mismatch");
if (certificate.inputs.compiledArtifactSha256 !== sha(artifactBytes)) throw new Error("artifact hash mismatch");
if (certificate.transcript.sha256 !== sha(transcript)) throw new Error("transcript hash mismatch");
if (!transcript.toString("utf8").includes("11 passing")) throw new Error("test transcript mismatch");

const runtime = Buffer.from(artifact.deployedBytecode.slice(2), "hex");
if (certificate.compiledRuntime.bytes !== runtime.length || certificate.compiledRuntime.sha256 !== sha(runtime)) throw new Error("runtime mismatch");
const opcodes = [];
for (let i = 0; i < runtime.length; i += 1) {
  const opcode = runtime[i];
  opcodes.push(opcode);
  if (opcode >= 0x60 && opcode <= 0x7f) i += opcode - 0x5f;
}
for (const [name, opcode] of [["CALLCODE", 0xf2], ["DELEGATECALL", 0xf4], ["CREATE", 0xf0], ["CREATE2", 0xf5], ["SELFDESTRUCT", 0xff]]) {
  if (opcodes.includes(opcode)) throw new Error(`forbidden executable opcode ${name}`);
}
const functions = artifact.abi.filter((item) => item.type === "function").map((item) => item.name);
for (const forbidden of ["cancel", "refund", "upgradeTo", "upgradeToAndCall", "changeAdmin"]) {
  if (functions.includes(forbidden)) throw new Error(`forbidden entry ${forbidden}`);
}
for (const required of ["openOrder", "submitShare", "withdrawCredit"]) {
  if (!functions.includes(required)) throw new Error(`missing entry ${required}`);
}
if (certificate.certifiedMinimumOutflowWei !== "10000000000000000000") throw new Error("outflow mismatch");
console.log("PREFUNDED_THRESHOLD_EXCHANGE_OFFLINE=PASS");

