import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const started = Date.now();
function run(command, args, cwd = root, env = process.env) {
  const result = spawnSync(command, args, { cwd, stdio: "inherit", shell: false, env: { ...env, PYTHONDONTWRITEBYTECODE: "1" } });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
function python(args, cwd) {
  const candidates = process.platform === "win32"
    ? [["py", ["-3"]], ["python3", []], ["python", []]]
    : [["python3", []], ["python", []]];
  for (const [command, prefix] of candidates) {
    const probe = spawnSync(command, [...prefix, "--version"], { stdio: "ignore", shell: false });
    if (!probe.error && probe.status === 0) return run(command, [...prefix, ...args], cwd);
  }
  throw new Error("Python 3 not found");
}
console.log("INTEGRITY_DRIVER=v49");
console.log("FORMAL_MODE=PRESERVED_PROOF_HASH_AND_SEMANTIC_VERIFICATION_NOT_REEXECUTION");
run(process.execPath, ["build_manifest.mjs", "--check"]);
run(process.execPath, ["verify_freeze_evidence.mjs"], path.join(root, "threshold_deployment_audit"));
run(process.execPath, ["verify_offline_v49.mjs"], path.join(root, "threshold_deployment_audit"));
run(process.execPath, ["scripts/verify_raw_capture_v48.mjs"], path.join(root, "threshold_deployment_audit"));
python(["verify_offline.py"], path.join(root, "production_snapshot"));
const evidenceRoot = path.join(root, "evidence_admission");
python(["scripts/run_floor_admission_experiment.py"], evidenceRoot);
python(["scripts/run_refresh_window_experiment.py"], evidenceRoot);
python(["-m", "unittest", "tests.test_evidence_admission_and_refresh", "-v"], evidenceRoot);
const refinementRoot = path.join(root, "joint_incidence_refinement");
run(process.execPath, ["verify_deployment_admission.mjs"], refinementRoot);
run(process.execPath, ["verify_deployment_admission_negative.mjs"], refinementRoot);
run(process.execPath, ["verify_refinement.mjs"], refinementRoot);
run(process.execPath, ["verify_prefunded_exchange.mjs"], refinementRoot);
python(["verify_schema_independent.py"], refinementRoot);
python(["verify_unbridged_member_loss_proxies.py"], path.join(root, "core_formula_checks"));
run(process.execPath, ["build_manifest.mjs", "--check"]);
console.log(`INTEGRITY_VERIFICATION_SECONDS=${Math.ceil((Date.now() - started) / 1000)}`);
console.log("V49_INTEGRITY_AND_PRESERVED_PROOFS=PASS");
