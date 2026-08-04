import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseJsonRejectingDuplicateKeys } from "./scripts/finite_lts_v2.mjs";
import {
  canonicalJson,
  evaluateFrontier,
  solveRepairCatalog,
  validateCountermodelBinding,
} from "./scripts/evidence_frontier_v50.mjs";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const read = async (relative) => parseJsonRejectingDuplicateKeys(await readFile(path.join(ROOT, relative), "utf8"), relative);
const clone = (value) => structuredClone(value);
const hashScope = (scope) => createHash("sha256").update(canonicalJson(scope)).digest("hex");

const catalog = await read("data/countermodel_catalog.v1.json");
const entry = catalog.entries.find((candidate) => candidate.recordId === "gnosis-shutter-set10");
const record = await read(entry.recordPath);
const lts = await read(entry.ltsPath);
let rejectedBindings = 0;
let rejectedCatalogs = 0;

function rejectBinding(name, mutate, pattern) {
  const r = clone(record);
  const g = clone(lts);
  const e = clone(entry);
  mutate(r, g, e);
  assert.throws(() => validateCountermodelBinding(r, g, e), pattern, name);
  rejectedBindings += 1;
}

rejectBinding("scope hash tamper", (_r, _g, e) => { e.scopeSha256 = "0".repeat(64); }, /scope hash mismatch/);
rejectBinding("undeclared route phrase", (r, _g, e) => {
  r.scope.mechanismLanguage = "contract calls only";
  e.scopeSha256 = hashScope(r.scope);
}, /route phrase is not declared/);
rejectBinding("B5 proof invalidates absence basis", (r) => { r.gates.B5.evidence.push({ type: "hypothetical" }); }, /admitted B5 object/);
rejectBinding("named acquirer mismatch", (_r, g) => { g.namedAcquirer = "different-buyer"; }, /named acquirer mismatch/);
rejectBinding("numeraire mismatch", (_r, g) => { g.numeraire.asset = "different-asset"; }, /numeraire.asset mismatch/);
rejectBinding("nonminimal witness shape", (_r, g) => { g.states.push("unused"); }, /two-state one-transition/);
rejectBinding("route slug mismatch", (_r, g) => { g.transitions[0].route = "different-route"; }, /route slug/);
rejectBinding("mapped route is not a B5 counterexample", (_r, g) => { g.mappedRoutes.push(g.transitions[0].route); }, /route is already mapped/);
rejectBinding("unusable output", (_r, g) => { g.transitions[0].usableDelivery = false; }, /usable-delivery predicate/);
rejectBinding("positive outflow is not a zero countermodel", (_r, g) => {
  g.transitions[0].buyerDebit = 1;
  g.transitions[0].debitOrigin = g.namedAcquirer;
  g.transitions[0].irreversible = true;
}, /does not have zero named-acquirer outflow/);
rejectBinding("no successful acquisition", (_r, g) => { g.transitions[0].success = false; }, /success must be unique|no reachable successful/);

const repair = await read("data/repair_catalog.v1.json");
const solved = solveRepairCatalog(repair);
assert.equal(solved.challengeCount, 8);
assert.equal(solved.minimumFamilyCount, 3);
assert.deepEqual(solved.minimumSolutions, [["pathwise-completion-witness", "deployment-coverage-proof", "closed-exchange-proof-family"]]);

function rejectCatalog(name, mutate, pattern) {
  const candidate = clone(repair);
  mutate(candidate);
  assert.throws(() => solveRepairCatalog(candidate), pattern, name);
  rejectedCatalogs += 1;
}

rejectCatalog("duplicate challenge", (candidate) => { candidate.challenges.push(clone(candidate.challenges[0])); }, /duplicate repair challenge/);
rejectCatalog("unknown challenge coverage", (candidate) => { candidate.candidateFamilies[0].covers.push("UNKNOWN"); }, /unknown challenge/);
rejectCatalog("uncoverable deployment witness", (candidate) => {
  candidate.candidateFamilies = candidate.candidateFamilies.filter((family) => family.id !== "deployment-coverage-proof");
}, /cannot cover all challenges/);

const result = await evaluateFrontier();
assert.equal(result.sourceCorpus.totalFilesRehashed, 36);
assert.equal(result.publicRecords, 4);
assert.equal(result.gateCellsScreened, 20);
assert.equal(result.admittedGateEvidenceObjects, 0);
assert.equal(result.exactZeroCompatibleCountermodels, 4);
assert.equal(result.repairFrontier.minimumFamilyCount, 3);
for (const countermodel of result.countermodels) {
  assert.equal(countermodel.shortestNamedAcquirerOutflow, 0);
  assert.equal(countermodel.b1UsableDelivery, "PASS");
  assert.equal(countermodel.b5AlternativeRoute, "FAIL_COUNTEREXAMPLE");
}

console.log(`COUNTERMODEL_BINDING_REJECTIONS=${rejectedBindings}`);
console.log(`REPAIR_CATALOG_REJECTIONS=${rejectedCatalogs}`);
console.log("EVIDENCE_FRONTIER_V50_TESTS=PASS");
