import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const hardhat = path.join(ROOT, "node_modules", "hardhat", "dist", "src", "cli.js");
const run = spawnSync(process.execPath, [hardhat, "test"], { cwd: ROOT, encoding: "utf8", shell: false, env: process.env });
const transcript = `${run.stdout ?? ""}${run.stderr ?? ""}`.replaceAll(ROOT, "<ARTIFACT_ROOT>");
if (run.error) throw run.error;
if (run.status !== 0 || !transcript.includes("PrefundedThresholdExchange positive bridge") || !transcript.includes("11 passing")) {
  process.stderr.write(transcript);
  process.exit(run.status ?? 1);
}

const sourcePath = path.join(ROOT, "contracts", "PrefundedThresholdExchange.sol");
const registryPath = path.join(ROOT, "contracts", "test", "MockThresholdBridgeDependencies.sol");
const testPath = path.join(ROOT, "test", "PrefundedThresholdExchange.ts");
const artifactPath = path.join(ROOT, "artifacts", "contracts", "PrefundedThresholdExchange.sol", "PrefundedThresholdExchange.json");
const [source, registry, test, artifactBytes] = await Promise.all([
  readFile(sourcePath), readFile(registryPath), readFile(testPath), readFile(artifactPath),
]);
const artifact = JSON.parse(artifactBytes);
const rawRuntime = Buffer.from(artifact.deployedBytecode.slice(2), "hex");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");

const results = path.join(ROOT, "results");
await mkdir(results, { recursive: true });
const logPath = path.join(results, "prefunded_threshold_exchange.log");
await writeFile(logPath, transcript, "utf8");
const certificate = {
  schema: "prefunded-threshold-exchange-test/v1",
  status: "PASS",
  constructionBoundary: "contract-language only; usable-share verifier, threshold-set registry, funding provenance, beneficial-control separation, and off-contract routes remain external evidence",
  certifiedMinimumOutflowWei: "10000000000000000000",
  namedTestCases: 5,
  fullSuitePassing: 11,
  inputs: {
    sourceSha256: sha(source),
    mockDependenciesSha256: sha(registry),
    testSha256: sha(test),
    compiledArtifactSha256: sha(artifactBytes),
  },
  compiledRuntime: {
    bytes: rawRuntime.length,
    sha256: sha(rawRuntime),
  },
  transcript: {
    path: "results/prefunded_threshold_exchange.log",
    sha256: sha(Buffer.from(transcript)),
  },
};
await writeFile(path.join(results, "prefunded_threshold_exchange.json"), `${JSON.stringify(certificate, null, 2)}\n`, "utf8");
console.log("PREFUNDED_THRESHOLD_EXCHANGE_TESTS=PASS");

