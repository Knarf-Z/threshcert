import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { isPositiveAmount, parseExactAmount } from "./scripts/finite_lts_v2.mjs";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const parse = (bytes) => JSON.parse(bytes.toString("utf8").replace(/^\uFEFF/, ""));
const evaluator = path.join(ROOT, "scripts", "evaluate_offline_v49.mjs");
const run = spawnSync(process.execPath, [evaluator], { cwd: ROOT, encoding: "utf8" });
if (run.status !== 0) throw new Error(`evaluator failed\n${run.stdout}\n${run.stderr}`);
if (!run.stdout.includes("EXACT_CANONICAL_RATIONAL_ARITHMETIC=PASS")) throw new Error("evaluator exact-amount self-test missing");
const schemaTests = spawnSync(process.execPath, [path.join(ROOT, "test_finite_lts_v2.mjs")], { cwd: ROOT, encoding: "utf8" });
if (schemaTests.status !== 0 || !schemaTests.stdout.includes("FINITE_LTS_V2_NEGATIVE_AND_FRACTION_TESTS=PASS")) {
  throw new Error(`finite-LTS schema tests failed\n${schemaTests.stdout}\n${schemaTests.stderr}`);
}
const generated = await readFile(path.join(ROOT, "results", "bridge_audit.generated.json"));
const canonical = await readFile(path.join(ROOT, "results", "bridge_audit.v3.json"));
if (!generated.equals(canonical)) throw new Error(`generated/canonical byte mismatch: ${sha(generated)} != ${sha(canonical)}`);

const result = parse(canonical);
const policy = parse(await readFile(path.join(ROOT, "policy.public-evidence.v3.json")));
const evaluatorText = await readFile(evaluator, "utf8");
const recordDir = path.join(ROOT, "data", "records_v49");
const recordFiles = (await readdir(recordDir)).filter((name) => name.endsWith(".json")).sort();
const inputs = [];
for (const name of recordFiles) inputs.push(parse(await readFile(path.join(recordDir, name))));
for (const record of inputs.filter((record) => record.recordType === "public-deployment")) {
  const forbidden = [record.id, record.scope.system].filter((value) => typeof value === "string" && value.length > 3);
  for (const value of forbidden) if (evaluatorText.toLowerCase().includes(value.toLowerCase())) throw new Error(`evaluator hardcodes ${value}`);
}
if (result.publicDeploymentCount !== 4) throw new Error("unexpected public cohort size");
if (result.positivePublicDeploymentCertificates !== 0) throw new Error("unexpected positive public certificate");
const compiledById = new Map(result.records.map((record) => [record.id, record]));
for (const input of inputs) {
  const compiled = compiledById.get(input.id);
  if (!compiled) throw new Error(`${input.id}: omitted by compiler`);
  if (input.recordType === "public-deployment" && compiled.status !== "FAIL_CLOSED_MISSING_EVIDENCE") throw new Error(`${input.id}: public missing-evidence status changed`);
  if (input.recordType === "public-deployment") {
    for (const gate of policy.bridgeGates.map((entry) => entry.id)) {
      if (input.gates[gate].evidence.length !== 0) throw new Error(`${input.id}/${gate}: public worked case unexpectedly contains gate evidence`);
    }
  }
  for (const gate of policy.bridgeGates.map((entry) => entry.id)) {
    if (!compiled.gates[gate]) throw new Error(`${input.id}: missing compiled ${gate}`);
    if (!compiled.gates[gate].context.every((ref) => ref.path && ref.sourceSha256 && ref.pointer !== undefined)) throw new Error(`${input.id}/${gate}: unbound context reference`);
  }
}
const pass = result.records.find((record) => record.recordType === "constructed-diagnostic" && record.status === "PASS");
if (!pass || pass.certifiedNamedAcquirerNetIrreversibleOutflow !== 4) throw new Error("finite positive witness is not exact at four accounting units");
if (pass.certificateDerivation?.type !== "shortest-successful-path" || pass.certificateDerivation.value !== 4 || !pass.certificateDerivation.sourceRef) {
  throw new Error("finite positive witness is not compiler-derived from a shortest successful LTS path");
}
if (!pass.gates.B1.evidenceResults[0].detail.startsWith("2 reachable success")) {
  throw new Error("finite positive witness does not exercise two successful paths");
}
for (const name of ["bridge_pass_lts.v2.json", "near_pass_lts.v2.json"]) {
  const lts = parse(await readFile(path.join(ROOT, "data", "constructed", name)));
  const outgoingStates = new Set(lts.transitions.map((transition) => transition.from));
  if (lts.transitions.some((transition) => transition.success === true && outgoingStates.has(transition.to))) throw new Error(`${name}: success is not accounting-window terminal`);
  if (lts.transitions.some((transition) => isPositiveAmount(parseExactAmount(transition.buyerPrefund)) && transition.prefundOrigin !== lts.namedAcquirer)) throw new Error(`${name}: prefund origin is not the named acquirer`);
}
for (const record of result.records.filter((entry) => entry.status !== "PASS")) {
  if (record.certificateDerivation?.type !== "fail-closed-zero" || record.certifiedNamedAcquirerNetIrreversibleOutflow !== 0) {
    throw new Error(`${record.id}: non-admitted record did not fail closed to a derived zero`);
  }
}
const near = result.records.find((record) => record.recordType === "constructed-diagnostic" && record.status === "FAIL_COUNTEREXAMPLE");
if (!near) throw new Error("missing discriminative near-pass");
for (const gate of ["B1", "B2", "B3", "B4"]) if (near.gates[gate].status !== "PASS") throw new Error(`near-pass ${gate} should pass`);
if (near.gates.B5.status !== "FAIL_COUNTEREXAMPLE" || near.gates.B5.evidenceResults[0].witness !== "off-contract-leak") throw new Error("near-pass B5 witness missing");

// Exhaustive monotonicity check for truth-consistent positive evidence refinements.
const weak = ["FAIL_CLOSED_MISSING_EVIDENCE", "UNKNOWN"];
const strong = ["PASS", "NOT_APPLICABLE"];
const cert = (vector) => vector.every((status) => strong.includes(status)) ? 1 : 0;
let comparisons = 0;
for (let mask = 0; mask < (1 << 5); mask += 1) {
  for (let upgrade = 0; upgrade < (1 << 5); upgrade += 1) {
    const before = Array.from({ length: 5 }, (_, i) => weak[(mask >> i) & 1]);
    const after = before.map((status, i) => (upgrade >> i) & 1 ? strong[(mask >> i) & 1] : status);
    if (cert(after) < cert(before)) throw new Error("positive-evidence monotonicity violation");
    comparisons += 1;
  }
}
console.log(run.stdout.trim());
console.log(schemaTests.stdout.trim());
console.log(`CANONICAL_SHA256=${sha(canonical)}`);
console.log(`MONOTONICITY_COMPARISONS=${comparisons}`);
console.log("FINITE_LTS_EVIDENCE_CHECKER_OFFLINE=PASS");
