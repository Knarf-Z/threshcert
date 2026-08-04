import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
console.log("ARCHIVAL_DRIVER=includes exploratory and withdrawn modules not used by the v49 paper");
function run(command, args, cwd = root) {
  const env = { ...process.env, PYTHONDONTWRITEBYTECODE: "1" };
  const r = spawnSync(command, args, { cwd, stdio: "inherit", shell: false, env });
  if (r.error) throw r.error;
  if (r.status !== 0) process.exit(r.status ?? 1);
}
function python(args, cwd) {
  for (const [cmd, prefix] of [["python", []], ["python3", []], ["py", ["-3"]]]) {
    const probe = spawnSync(cmd, [...prefix, "--version"], { stdio: "ignore", shell: false });
    if (!probe.error && probe.status === 0) return run(cmd, [...prefix, ...args], cwd);
  }
  throw new Error("Python 3 not found");
}

run(process.execPath, ["build_manifest.mjs", "--check"]);
run(process.execPath, ["verify_freeze_evidence.mjs"], path.join(root, "threshold_deployment_audit"));
python(["verify_offline.py"], path.join(root, "production_snapshot"));
const evidenceRoot = path.join(root, "evidence_admission");
python(["scripts/run_floor_admission_experiment.py"], evidenceRoot);
python(["scripts/run_refresh_window_experiment.py"], evidenceRoot);
python(["-m", "unittest", "tests.test_evidence_admission_and_refresh", "-v"], evidenceRoot);
console.log("EXPLORATORY_NOT_USED_BY_V49=chiado_public_runs");
run(process.execPath, ["scripts/verify-preserved.mjs"], path.join(root, "chiado_public_runs"));
run(process.execPath, ["verify_deployment_admission.mjs"], path.join(root, "joint_incidence_refinement"));
run(process.execPath, ["verify_deployment_admission_negative.mjs"], path.join(root, "joint_incidence_refinement"));
run(process.execPath, ["verify_refinement.mjs"], path.join(root, "joint_incidence_refinement"));
run(process.execPath, ["verify_prefunded_exchange.mjs"], path.join(root, "joint_incidence_refinement"));
python(["verify_schema_independent.py"], path.join(root, "joint_incidence_refinement"));
run(process.execPath, ["verify_offline_v49.mjs"], path.join(root, "threshold_deployment_audit"));
run(process.execPath, ["scripts/verify_raw_capture_v48.mjs"], path.join(root, "threshold_deployment_audit"));
console.log("EXPLORATORY_NOT_USED_BY_V49=third_party_contract_survey");
const surveyRoot = path.join(root, "third_party_contract_survey");
run(process.execPath, ["test_screen_contract_v2.mjs"], surveyRoot);
run(process.execPath, ["aggregate_results_v2.mjs"], surveyRoot);
run(process.execPath, ["verify_manifest_v2.mjs"], surveyRoot);
console.log("ARCHIVAL_FORMULA_FAMILIES_NOT_USED_BY_V49=begin");
for (const script of [
  "test_equivalence.py",
  "information_boundary.py",
  "partial_activation_evidence.py",
  "atomic_bypass_hierarchy.py",
  "evidence_optimal_atomic_bypass.py",
  "mixed_evidence_atomic_bypass.py",
  "common_solvency_separation.py",
  "refinement_quantifier_boundaries.py",
  "reproduce_paper_numbers.py",
]) python([script], path.join(root, "core_formula_checks"));
console.log("ARTIFACT_ALL_CORE_CHECKS=PASS");
