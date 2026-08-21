import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const hardhat = path.join(ROOT, "node_modules", "hardhat", "dist", "src", "cli.js");
const run = spawnSync(process.execPath, [hardhat, "test"], {
  cwd: ROOT,
  encoding: "utf8",
  shell: false,
  env: process.env,
});
const transcript = `${run.stdout ?? ""}${run.stderr ?? ""}`.replaceAll(ROOT, "<ARTIFACT_ROOT>").trimEnd() + "\n";
if (run.error) throw run.error;
if (
  run.status !== 0
  || !transcript.includes("GlobalNamedAcquirerToy finite-world bridge")
  || !transcript.includes("18 passing")
) {
  process.stderr.write(transcript);
  process.exit(run.status ?? 1);
}

const sourcePath = path.join(ROOT, "contracts", "GlobalNamedAcquirerToy.sol");
const testPath = path.join(ROOT, "test", "GlobalNamedAcquirerToy.ts");
const artifactPath = path.join(
  ROOT,
  "artifacts",
  "contracts",
  "GlobalNamedAcquirerToy.sol",
  "GlobalNamedAcquirerToy.json",
);
const [source, test, artifactBytes] = await Promise.all([
  readFile(sourcePath),
  readFile(testPath),
  readFile(artifactPath),
]);
const artifact = JSON.parse(artifactBytes);
const runtime = Buffer.from(artifact.deployedBytecode.slice(2), "hex");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const canonical = (value) => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
};
const semanticArtifact = { ...artifact };
delete semanticArtifact.buildInfoId;
const artifactSemanticSha256 = sha(Buffer.from(JSON.stringify(canonical(semanticArtifact))));
const results = path.join(ROOT, "results");
await mkdir(results, { recursive: true });
const logPath = path.join(results, "global_named_acquirer_toy_evm.log");
await writeFile(logPath, transcript, "utf8");
const evidence = {
  schema: "global-named-acquirer-toy-evm/v1",
  status: "PASS",
  fullSuitePassing: 18,
  namedTestCases: 6,
  inputs: {
    sourceSha256: sha(source),
    testSha256: sha(test),
    compiledArtifactSemanticSha256: artifactSemanticSha256,
  },
  compiledRuntime: {
    bytes: runtime.length,
    sha256: sha(runtime),
  },
  transcript: {
    path: "results/global_named_acquirer_toy_evm.log",
    sha256: sha(Buffer.from(transcript)),
  },
};
await writeFile(
  path.join(results, "global_named_acquirer_toy_evm.json"),
  `${JSON.stringify(evidence, null, 2)}\n`,
  "utf8",
);
console.log("GLOBAL_NAMED_ACQUIRER_TOY_EVM_CAPTURE=PASS");
