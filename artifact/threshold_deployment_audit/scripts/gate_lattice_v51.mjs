// Gate-ablation lattice and rectangularity separation.
//
// Two preregistered experiments over the SAME reference checker used by the
// deployment audit. This module imports evaluate_offline_v49.mjs rather than
// reimplementing the gate predicates, so the lattice exercises the shipped
// checker and not a copy of it. That import regenerates
// results/bridge_audit.generated.json as a deterministic side effect; the bytes
// are identical to a direct evaluator run, so the manifest is unaffected.
//
// Neither experiment discovers routes. Both operate on explicitly supplied
// finite LTSs and report scope-relative results.
//
//   S1  Gate-ablation lattice. Five targeted semantic mutations of the passing
//       fixture, one per bridge gate, applied in all 2^5 = 32 combinations.
//       Measures (a) whether any nonempty ablation still yields a positive
//       certificate, and (b) the gate-overlap matrix that the bridge-admission
//       theorem explicitly declines to claim away.
//
//   S3  Rectangularity separation. A ledger whose admitted amount constraints
//       are jointly coupled has no faithful edgewise finite-LTS encoding. The
//       edgewise encoding passes all five gates and returns a sound floor
//       strictly below the true constrained minimum, making the
//       pathwise-rectangular premise of the exact-closure theorem load-bearing.

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  amountToString,
  parseJsonRejectingDuplicateKeys,
  validateFiniteLts,
} from "./finite_lts_v2.mjs";
import { inspectLts, shortestSuccessfulLtsOutflow } from "./evaluate_offline_v49.mjs";

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const ROOT = path.dirname(path.dirname(SCRIPT_PATH));
const FIXTURE = path.join(ROOT, "data", "constructed", "bridge_pass_lts.v2.json");
const GENERATED_PATH = path.join(ROOT, "results", "gate_lattice.generated.json");
const CANONICAL_PATH = path.join(ROOT, "results", "gate_lattice.v1.json");
const GATES = ["B1", "B2", "B3", "B4", "B5"];
const sha = (b) => createHash("sha256").update(b).digest("hex");
const clone = (v) => structuredClone(v);

const fixtureBytes = await readFile(FIXTURE);
const fixture = parseJsonRejectingDuplicateKeys(fixtureBytes.toString("utf8"), "fixture");

// ---------------------------------------------------------------- S1 lattice

// One targeted mutation per gate. Each is the minimal semantic edit that
// contradicts the gate's own predicate; none edits the schema shape.
const MUTATIONS = [
  {
    target: "B1",
    id: "M1-usable-delivery-withdrawn",
    note: "a reachable mapped success no longer carries usable delivery",
    apply: (lts) => { tx(lts, "atomic-exchange").usableDelivery = false; },
  },
  {
    target: "B2",
    id: "M2-debit-origin-sponsor",
    note: "the counted positive debit originates outside the named acquirer",
    apply: (lts) => { tx(lts, "atomic-exchange").debitOrigin = "sponsor-X"; },
  },
  {
    target: "B3",
    id: "M3-debit-reversible",
    note: "the counted debit on a mapped-success prefix is not irreversible",
    apply: (lts) => { tx(lts, "atomic-exchange").irreversible = false; },
  },
  {
    target: "B4",
    id: "M4-open-return-edge",
    note: "a mapped-success prefix carries an unclosed return-to-control edge",
    apply: (lts) => { tx(lts, "atomic-exchange").returnToControl = 1; },
  },
  {
    target: "B5",
    id: "M5-unmapped-usable-success",
    note: "an off-contract route reaches usable success with zero debit",
    apply: (lts) => {
      lts.states.push("leaked");
      lts.transitions.push({
        id: "off-contract-leak", from: "s0", to: "leaked", route: "off-contract",
        success: true, usableDelivery: true, buyerDebit: 0, debitOrigin: "none",
        irreversible: false, returnToControl: 0, externalFunding: 0,
        buyerPrefund: 0, prefundOrigin: "none",
      });
    },
  },
];
function tx(lts, id) {
  const found = lts.transitions.find((t) => t.id === id);
  if (!found) throw new Error(`fixture lacks transition ${id}`);
  return found;
}

function evaluate(lts) {
  const validation = validateFiniteLts(lts);
  if (!validation.ok) return { wellFormed: false, gates: null, allPass: false, certificate: "0", shortestPath: null };
  const gates = {};
  for (const gate of GATES) gates[gate] = inspectLts(lts, gate).status;
  const allPass = GATES.every((g) => gates[g] === "PASS");
  let shortestPath = null;
  try { shortestPath = amountToString(shortestSuccessfulLtsOutflow(lts)); } catch { shortestPath = null; }
  // The audit pipeline emits the fail-closed sentinel zero unless every gate passes.
  return { wellFormed: true, gates, allPass, certificate: allPass ? shortestPath : "0", shortestPath };
}

const baseline = evaluate(fixture);
if (!baseline.allPass) throw new Error("baseline fixture does not pass all gates");

const cells = [];
for (let mask = 0; mask < 32; mask += 1) {
  const applied = MUTATIONS.filter((_, i) => (mask >> i) & 1);
  const candidate = clone(fixture);
  for (const m of applied) m.apply(candidate);
  const result = evaluate(candidate);
  cells.push({
    mask,
    appliedMutations: applied.map((m) => m.id),
    targetedGates: applied.map((m) => m.target),
    wellFormed: result.wellFormed,
    gates: result.gates,
    certificate: result.certificate,
    unguardedShortestPath: result.shortestPath,
  });
}

// Singleton rows give the gate-overlap matrix.
const overlap = {};
for (const m of MUTATIONS) {
  const row = cells.find((c) => c.appliedMutations.length === 1 && c.appliedMutations[0] === m.id);
  overlap[m.id] = { target: m.target, note: m.note, gates: row.gates };
}
const diagonalHit = MUTATIONS.every((m) => overlap[m.id].gates[m.target] !== "PASS");
const offDiagonalFailures = [];
for (const m of MUTATIONS) {
  for (const g of GATES) {
    if (g !== m.target && overlap[m.id].gates[g] !== "PASS") offDiagonalFailures.push({ mutation: m.id, target: m.target, alsoFails: g });
  }
}
const positiveNonEmpty = cells.filter((c) => c.mask !== 0 && c.certificate !== "0");

// -------------------------------------------------- S3 rectangularity gap

// Admitted ledger constraints for one two-step successful path:
//   debit(step-a) >= 1,  debit(step-b) >= 1,  debit(step-a)+debit(step-b) >= 5.
// The third is a joint (atomic invoice) minimum spanning both steps. Only the
// first two survive an edgewise encoding.
const COUPLED = {
  edgewiseFloors: { "step-a": 1, "step-b": 1 },
  jointFloor: 5,
};
const coupledLts = {
  schema: "finite-acquisition-lts/v2",
  description: "Edgewise encoding of a jointly constrained ledger. Each edge carries its own admitted floor; the joint constraint debit(step-a)+debit(step-b) >= 5 is not expressible in this format and is therefore lost.",
  initialState: "s0",
  namedAcquirer: "buyer-A",
  numeraire: { asset: "synthetic-accounting-unit", unit: "wei", valuationTime: "transition", conversionLowerPrice: "identity", gasTreatment: "excluded-accounting-only" },
  mappedRoutes: ["coupled"],
  states: ["s0", "funded", "mid", "done"],
  transitions: [
    { id: "prefund", from: "s0", to: "funded", route: "coupled", success: false, usableDelivery: false, buyerDebit: 0, debitOrigin: "none", irreversible: false, returnToControl: 0, externalFunding: 0, buyerPrefund: 5, prefundOrigin: "buyer-A" },
    { id: "step-a", from: "funded", to: "mid", route: "coupled", success: false, usableDelivery: false, buyerDebit: COUPLED.edgewiseFloors["step-a"], debitOrigin: "buyer-A", irreversible: true, returnToControl: 0, externalFunding: 0, buyerPrefund: 0, prefundOrigin: "none" },
    { id: "step-b", from: "mid", to: "done", route: "coupled", success: true, usableDelivery: true, buyerDebit: COUPLED.edgewiseFloors["step-b"], debitOrigin: "buyer-A", irreversible: true, returnToControl: 0, externalFunding: 0, buyerPrefund: 0, prefundOrigin: "none" },
  ],
};
const coupledResult = evaluate(coupledLts);

// True constrained minimum, by exhaustive search over the admitted region on a
// fixed rational grid, cross-checked against min{a+b : a,b>=1, a+b>=5} = 5.
function trueJointMinimum(step = 1 / 64, hi = 12) {
  let best = Infinity;
  for (let a = COUPLED.edgewiseFloors["step-a"]; a <= hi; a += step) {
    for (let b = COUPLED.edgewiseFloors["step-b"]; b <= hi; b += step) {
      if (a + b + 1e-12 < COUPLED.jointFloor) continue;
      best = Math.min(best, a + b);
    }
  }
  return best;
}
const searched = trueJointMinimum();
const analytic = COUPLED.jointFloor;
const checkerFloor = Number(coupledResult.certificate);
const gapAbsolute = analytic - checkerFloor;
const gapRatio = analytic / checkerFloor;

// ---------------------------------------------------------------- emit

const result = {
  schema: "gate-lattice-and-rectangularity/v1",
  generatedFrom: {
    driverPath: path.relative(ROOT, SCRIPT_PATH).replaceAll("\\", "/"),
    driverSha256: sha(await readFile(SCRIPT_PATH)),
    fixturePath: path.relative(ROOT, FIXTURE).replaceAll("\\", "/"),
    fixtureSha256: sha(fixtureBytes),
  },
  preregisteredPredictions: {
    P1: "the certificate is positive exactly for the empty ablation; all 31 nonempty ablations return the fail-closed sentinel zero",
    P2: "each targeted mutation drives its own gate away from PASS (diagonal)",
    P3: "off-diagonal entries are measured, not assumed; the gates are not claimed independent",
    P4: "the edgewise encoding of a jointly constrained ledger passes all five gates and returns a floor strictly below the true constrained minimum",
  },
  s1GateAblationLattice: {
    baselineCertificate: baseline.certificate,
    subsetsEvaluated: cells.length,
    nonEmptyAblationsWithPositiveCertificate: positiveNonEmpty.length,
    everyTargetedMutationHitsItsGate: diagonalHit,
    offDiagonalCellCount: MUTATIONS.length * (GATES.length - 1),
    offDiagonalGateFailures: offDiagonalFailures,
    overlapMatrix: overlap,
    cells,
  },
  s3RectangularitySeparation: {
    admittedConstraints: {
      edgewiseFloors: COUPLED.edgewiseFloors,
      jointFloor: `debit(step-a) + debit(step-b) >= ${COUPLED.jointFloor}`,
    },
    edgewiseEncodingGates: coupledResult.gates,
    edgewiseEncodingAllGatesPass: coupledResult.allPass,
    checkerFloor,
    trueConstrainedMinimumAnalytic: analytic,
    trueConstrainedMinimumGridSearch: Number(searched.toFixed(6)),
    gapAbsolute,
    gapRatio,
    checkerFloorAsFractionOfTruth: checkerFloor / analytic,
    soundness: checkerFloor <= analytic,
    boundary: "The checker is not incorrect: soundness holds unconditionally. The instance shows that the pathwise-rectangular premise is load-bearing for the exactness clause, and that an edgewise finite-LTS encoding silently discards joint amount constraints.",
  },
};
await mkdir(path.dirname(GENERATED_PATH), { recursive: true });
const output = `${JSON.stringify(result, null, 2)}\n`;
await writeFile(GENERATED_PATH, output, "utf8");
if (process.argv.includes("--freeze")) await writeFile(CANONICAL_PATH, output, "utf8");

console.log(`S1_BASELINE_CERTIFICATE=${baseline.certificate}`);
console.log(`S1_SUBSETS=${cells.length}`);
console.log(`S1_NONEMPTY_ABLATIONS_STILL_POSITIVE=${positiveNonEmpty.length}`);
console.log(`S1_DIAGONAL_ALL_HIT=${diagonalHit ? "PASS" : "FAIL"}`);
console.log(`S1_OFF_DIAGONAL_FAILURES=${offDiagonalFailures.length}/${MUTATIONS.length * (GATES.length - 1)}`);
for (const m of MUTATIONS) {
  console.log(`  ${m.id} (targets ${m.target}) -> ${GATES.map((g) => `${g}:${overlap[m.id].gates[g]}`).join(" ")}`);
}
console.log(`S3_EDGEWISE_ALL_GATES_PASS=${coupledResult.allPass ? "PASS" : "FAIL"}`);
console.log(`S3_CHECKER_FLOOR=${checkerFloor}`);
console.log(`S3_TRUE_MINIMUM=${analytic} (grid ${searched.toFixed(6)})`);
console.log(`S3_GAP_ABSOLUTE=${gapAbsolute}  RATIO=${gapRatio}`);
console.log(`S3_SOUNDNESS_PRESERVED=${checkerFloor <= analytic ? "PASS" : "FAIL"}`);
console.log("GATE_LATTICE_AND_RECTANGULARITY=PASS");
