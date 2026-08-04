// Verifies the gate-ablation lattice and the rectangularity separation, and
// pins every number the manuscript quotes from them.
//
// Regenerates the result from the shipped driver, byte-compares it against the
// canonical record, then asserts each manuscript claim individually so that a
// drift between paper and artifact fails here rather than in review.

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const driver = path.join(ROOT, "scripts", "gate_lattice_v51.mjs");

const run = spawnSync(process.execPath, [driver], { cwd: ROOT, encoding: "utf8" });
if (run.status !== 0) throw new Error(`gate lattice driver failed\n${run.stdout}\n${run.stderr}`);
if (!run.stdout.includes("GATE_LATTICE_AND_RECTANGULARITY=PASS")) throw new Error("gate lattice sentinel missing");

const generated = await readFile(path.join(ROOT, "results", "gate_lattice.generated.json"));
const canonical = await readFile(path.join(ROOT, "results", "gate_lattice.v1.json"));
if (!generated.equals(canonical)) {
  throw new Error(`gate lattice generated/canonical byte mismatch: ${sha(generated)} != ${sha(canonical)}`);
}
const result = JSON.parse(canonical.toString("utf8"));
const s1 = result.s1GateAblationLattice;
const s3 = result.s3RectangularitySeparation;

// Each entry is a claim made in the manuscript text or tables.
const claims = [
  ["baseline fixture certifies four accounting units", s1.baselineCertificate === "4"],
  ["all 2^5 gate subsets are evaluated", s1.subsetsEvaluated === 32],
  ["no nonempty ablation retains a positive certificate", s1.nonEmptyAblationsWithPositiveCertificate === 0],
  ["every targeted mutation refutes its own gate", s1.everyTargetedMutationHitsItsGate === true],
  ["twenty off-diagonal cells exist", s1.offDiagonalCellCount === 20],
  ["exactly one off-diagonal cell fires", s1.offDiagonalGateFailures.length === 1],
  ["the single overlap is the B1 mutation also refuting B3",
    s1.offDiagonalGateFailures[0]?.target === "B1" && s1.offDiagonalGateFailures[0]?.alsoFails === "B3"],
  ["the edgewise encoding of the coupled ledger passes all five gates", s3.edgewiseEncodingAllGatesPass === true],
  ["the checker floor on the coupled ledger is two", s3.checkerFloor === 2],
  ["the true constrained minimum is five, analytically", s3.trueConstrainedMinimumAnalytic === 5],
  ["the grid search agrees at five", s3.trueConstrainedMinimumGridSearch === 5],
  ["the absolute gap is three", s3.gapAbsolute === 3],
  ["the ratio is 2.5", s3.gapRatio === 2.5],
  ["the returned floor is 40 percent of the truth", s3.checkerFloorAsFractionOfTruth === 0.4],
  ["soundness is preserved", s3.soundness === true],
];
const failed = claims.filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length > 0) throw new Error(`manuscript claim mismatch:\n  ${failed.join("\n  ")}`);

// The lattice must exercise the shipped checker, not a private copy.
const driverText = await readFile(driver, "utf8");
if (!driverText.includes("evaluate_offline_v49.mjs")) {
  throw new Error("gate lattice does not import the shipped evaluator");
}

console.log(run.stdout.trim());
console.log(`GATE_LATTICE_CANONICAL_SHA256=${sha(canonical)}`);
console.log(`MANUSCRIPT_CLAIMS_PINNED=${claims.length}`);
console.log("GATE_LATTICE_AND_RECTANGULARITY_OFFLINE=PASS");
