import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const refinement = path.join(root, "joint_incidence_refinement");
const started = Date.now();
function execute(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: options.cwd ?? root, encoding: options.capture ? "utf8" : undefined, stdio: options.capture ? "pipe" : "inherit", shell: false, env: options.env ?? process.env, timeout: options.timeout });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed (${result.status})\n${result.stdout ?? ""}\n${result.stderr ?? ""}`);
  return `${result.stdout ?? ""}${result.stderr ?? ""}`;
}
function probe(command, args) {
  const result = spawnSync(command, args, { stdio: "ignore", shell: false });
  return !result.error && result.status === 0;
}
function basePython() {
  if (process.env.V49_PYTHON) return { command: process.env.V49_PYTHON, prefix: [] };
  const candidates = process.platform === "win32" ? [["py", ["-3"]], ["python3", []], ["python", []]] : [["python3", []], ["python", []]];
  for (const [command, prefix] of candidates) if (probe(command, [...prefix, "--version"])) return { command, prefix };
  throw new Error("Python 3 not found; set V49_PYTHON");
}
async function halmosPython() {
  if (process.env.V49_PYTHON && probe(process.env.V49_PYTHON, ["-m", "halmos", "--version"])) return process.env.V49_PYTHON;
  const venv = path.join(root, ".runtime", "halmos-v49");
  const python = process.platform === "win32" ? path.join(venv, "Scripts", "python.exe") : path.join(venv, "bin", "python");
  if (!probe(python, ["-m", "halmos", "--version"])) {
    const base = basePython();
    await mkdir(path.dirname(venv), { recursive: true });
    execute(base.command, [...base.prefix, "-m", "venv", venv]);
    execute(python, ["-m", "pip", "install", "-r", path.join(refinement, "formal", "requirements-v48-portable.txt")], { timeout: 900000 });
    execute(python, ["-m", "pip", "install", "halmos==0.3.3", "--no-deps"], { timeout: 300000 });
  }
  const version = execute(python, ["-m", "halmos", "--version"], { capture: true });
  if (!version.includes("halmos 0.3.3")) throw new Error(`unexpected Halmos version: ${version}`);
  return python;
}
function forgePath() {
  const candidates = [process.env.FOUNDRY_BIN, "forge"];
  if (process.platform === "win32" && process.env.USERPROFILE) candidates.push(path.join(process.env.USERPROFILE, ".foundry", "bin", "forge.exe"));
  for (const candidate of candidates.filter(Boolean)) if (candidate === "forge" ? probe(candidate, ["--version"]) : existsSync(candidate) && probe(candidate, ["--version"])) return candidate;
  throw new Error("Foundry forge not found; install Foundry or set FOUNDRY_BIN");
}

console.log("REBUILD_DRIVER=v49");
console.log("FORMAL_MODE=FRESH_HALMOS_REEXECUTION");
const hardhat = path.join(refinement, "node_modules", "hardhat", "dist", "src", "cli.js");
if (!existsSync(hardhat)) execute(process.platform === "win32" ? "npm.cmd" : "npm", ["ci", "--no-audit", "--no-fund"], { cwd: refinement, timeout: 900000 });
execute(process.execPath, [hardhat, "compile", "--force"], { cwd: refinement, timeout: 300000 });
const admissionTemp = path.join(os.tmpdir(), `threshcert-v49-admission-${process.pid}.json`);
const testEnv = { ...process.env, DEPLOYMENT_ADMISSION_RESULT: admissionTemp };
const tests = execute(process.execPath, [hardhat, "test"], { cwd: refinement, capture: true, timeout: 300000, env: testEnv });
process.stdout.write(tests);
if (!tests.includes("11 passing") || !tests.includes("PrefundedThresholdExchange positive bridge")) throw new Error("Hardhat 11-test closure missing");
const freshAdmission = JSON.parse(await readFile(admissionTemp, "utf8"));
const canonicalAdmission = JSON.parse(await readFile(path.join(refinement, "results", "deployment_admission_local.json"), "utf8"));
if (!/^0x[0-9a-f]{64}$/i.test(freshAdmission.chain.blockHash) || freshAdmission.deployment.receiptBlockHash.toLowerCase() !== freshAdmission.chain.blockHash.toLowerCase()) throw new Error("fresh local block-hash relation failed");
const normalizeAdmission = (record) => {
  const copy = structuredClone(record);
  delete copy.chain.blockHash;
  delete copy.deployment.receiptBlockHash;
  return copy;
};
if (JSON.stringify(normalizeAdmission(freshAdmission)) !== JSON.stringify(normalizeAdmission(canonicalAdmission))) throw new Error("fresh deployment admission differs outside ephemeral local block hashes");
if (path.dirname(admissionTemp) !== path.resolve(os.tmpdir()) || !path.basename(admissionTemp).startsWith("threshcert-v49-admission-")) throw new Error("unsafe admission temp path");
await rm(admissionTemp, { force: true });
console.log("HARDHAT_RECOMPILE_11_TESTS_AND_ADMISSION_REGENERATION=PASS");

const python = await halmosPython();
const forge = forgePath();
const toolPath = [path.dirname(python), path.dirname(forge), process.env.PATH ?? ""].join(path.delimiter);
const proofEnv = { ...process.env, PATH: toolPath, PYTHONDONTWRITEBYTECODE: "1" };
const tempRoot = await mkdtemp(path.join(os.tmpdir(), "threshcert-v49-halmos-"));
try {
  execute(python, [path.join("scripts", "run_halmos_bridge.py"), "--jobs", "4", "--loop", "8", "--solver", "yices-2.6.4", "--results-dir", tempRoot], { cwd: refinement, env: proofEnv, timeout: 3600000 });
  const fresh = JSON.parse(await readFile(path.join(tempRoot, "halmos_evm_bridge.json"), "utf8"));
  const canonical = JSON.parse(await readFile(path.join(refinement, "results", "halmos_evm_bridge.json"), "utf8"));
  if (fresh.status !== "PASS" || fresh.proofCounts.totalProofs !== 82 || fresh.proofCounts.failed !== 0 || fresh.proofCounts.nonemptyBounds !== 0) throw new Error("fresh Halmos proof counts failed");
  if (Object.keys(fresh.proofs).length !== 82 || Object.values(fresh.proofs).some((proof) => !Array.isArray(proof.bounds) || proof.bounds.length !== 0)) throw new Error("fresh Halmos proof-name/bounds closure failed");
  if (JSON.stringify(fresh.inputs) !== JSON.stringify(canonical.inputs)) throw new Error("fresh Halmos input hashes differ from canonical");
  if (JSON.stringify(fresh.compiledRuntime) !== JSON.stringify(canonical.compiledRuntime)) throw new Error("fresh Halmos runtime differs from canonical");
  console.log("HALMOS_82_FRESH_PROOFS_0_FAILURES_0_BOUNDS=PASS");
} finally {
  const resolved = path.resolve(tempRoot);
  const tempBase = path.resolve(os.tmpdir());
  if (!resolved.startsWith(`${tempBase}${path.sep}`) || !path.basename(resolved).startsWith("threshcert-v49-halmos-")) throw new Error("refusing unsafe temp cleanup");
  await rm(resolved, { recursive: true, force: true });
}
execute(process.execPath, ["verify_offline_v49.mjs"], { cwd: path.join(root, "threshold_deployment_audit") });
execute(process.execPath, ["scripts/verify_raw_capture_v48.mjs"], { cwd: path.join(root, "threshold_deployment_audit") });
execute(process.execPath, ["verify_refinement.mjs"], { cwd: refinement });
execute(process.execPath, ["verify_prefunded_exchange.mjs"], { cwd: refinement });
execute(process.execPath, ["build_manifest.mjs", "--check"], { cwd: root });
console.log(`REBUILD_VERIFICATION_SECONDS=${Math.ceil((Date.now() - started) / 1000)}`);
console.log("V49_FRESH_REBUILD=PASS");
