import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  addAmount,
  amountToString,
  compareAmount,
  parseExactAmount,
  parseJsonRejectingDuplicateKeys,
  validateFiniteLts,
} from "./scripts/finite_lts_v2.mjs";
import {
  inspectLts,
  shortestSuccessfulLtsOutflow,
} from "./scripts/evaluate_offline_v49.mjs";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const fixtureRaw = await readFile(path.join(ROOT, "data", "constructed", "bridge_pass_lts.v2.json"), "utf8");
const fixture = parseJsonRejectingDuplicateKeys(fixtureRaw, "positive fixture");
const clone = (value) => structuredClone(value);
const gates = ["B1", "B2", "B3", "B4", "B5"];
let malformedCases = 0;
let rawRejectedCases = 0;
let semanticCases = 0;
let rationalCases = 0;
let boundaryCases = 0;

function assertMalformed(name, mutate) {
  const candidate = clone(fixture);
  mutate(candidate);
  const validation = validateFiniteLts(candidate);
  assert.equal(validation.ok, false, `${name}: schema unexpectedly accepted`);
  for (const gate of gates) assert.equal(inspectLts(candidate, gate).status, "UNKNOWN", `${name}/${gate}: must be UNKNOWN`);
  assert.throws(() => shortestSuccessfulLtsOutflow(candidate), /malformed finite LTS/, `${name}: shortest path must reject`);
  malformedCases += 1;
}

function assertRawRejected(name, raw) {
  assert.notEqual(raw, fixtureRaw, `${name}: raw mutation did not change input`);
  assert.throws(() => parseJsonRejectingDuplicateKeys(raw, name), /duplicate object member|canonical nonnegative safe integers|invalid value/);
  rawRejectedCases += 1;
}

for (const field of [
  "id", "from", "to", "route", "success", "usableDelivery", "buyerDebit",
  "debitOrigin", "irreversible", "returnToControl", "externalFunding",
  "buyerPrefund", "prefundOrigin",
]) {
  assertMalformed(`missing-transition-${field}`, (lts) => { delete lts.transitions[1][field]; });
}
for (const field of ["schema", "initialState", "namedAcquirer", "numeraire", "mappedRoutes", "states", "transitions"]) {
  assertMalformed(`missing-root-${field}`, (lts) => { delete lts[field]; });
}

assertMalformed("reported-missing-return-and-external", (lts) => {
  delete lts.transitions[1].returnToControl;
  delete lts.transitions[1].externalFunding;
});
assertMalformed("null-return-to-control", (lts) => { lts.transitions[1].returnToControl = null; });
assertMalformed("string-external-funding", (lts) => { lts.transitions[1].externalFunding = "0"; });
assertMalformed("floating-debit", (lts) => { lts.transitions[1].buyerDebit = 0.5; });
assertMalformed("negative-prefund", (lts) => { lts.transitions[0].buyerPrefund = -1; });
assertMalformed("unsafe-json-integer", (lts) => { lts.transitions[1].buyerDebit = Number.MAX_SAFE_INTEGER + 1; });
assertMalformed("nan-debit", (lts) => { lts.transitions[1].buyerDebit = Number.NaN; });
assertMalformed("infinite-debit", (lts) => { lts.transitions[1].buyerDebit = Number.POSITIVE_INFINITY; });
assertMalformed("wrong-boolean-type", (lts) => { lts.transitions[1].irreversible = 1; });
assertMalformed("unknown-typo-field", (lts) => {
  delete lts.transitions[1].externalFunding;
  lts.transitions[1].externalFundng = 0;
});
assertMalformed("zero-debit-origin-conflict", (lts) => {
  lts.transitions[1].buyerDebit = 0;
  lts.transitions[1].debitOrigin = lts.namedAcquirer;
});
assertMalformed("positive-prefund-origin-conflict", (lts) => { lts.transitions[0].prefundOrigin = "none"; });
assertMalformed("duplicate-state", (lts) => { lts.states.push(lts.states[0]); });
assertMalformed("duplicate-transition-id", (lts) => { lts.transitions[1].id = lts.transitions[0].id; });
assertMalformed("duplicate-mapped-route", (lts) => { lts.mappedRoutes.push(lts.mappedRoutes[0]); });
assertMalformed("unknown-endpoint", (lts) => { lts.transitions[1].to = "missing-state"; });
assertMalformed("unreduced-rational", (lts) => { lts.transitions[1].buyerDebit = { numerator: "2", denominator: "4" }; });
assertMalformed("zero-denominator", (lts) => { lts.transitions[1].buyerDebit = { numerator: "1", denominator: "0" }; });
assertMalformed("negative-rational-string", (lts) => { lts.transitions[1].buyerDebit = { numerator: "-1", denominator: "2" }; });
assertMalformed("rational-extra-key", (lts) => { lts.transitions[1].buyerDebit = { numerator: "1", denominator: "2", unit: "x" }; });

assertRawRejected("duplicate-transition-member", fixtureRaw.replace(
  '"externalFunding":0,"buyerPrefund":4',
  '"externalFunding":{"numerator":"1","denominator":"1"},"externalFunding":0,"buyerPrefund":4',
));
assertRawRejected("duplicate-root-member", fixtureRaw.replace(
  '"schema": "finite-acquisition-lts/v2",',
  '"schema": "finite-acquisition-lts/v2","schema": "finite-acquisition-lts/v2",',
));
for (const token of ["1e-400", "-1e-400", "0.0000001", "1e0", "NaN", "Infinity"]) {
  assertRawRejected(`raw-number-${token}`, fixtureRaw.replace('"externalFunding":0', `"externalFunding":${token}`));
}

{
  const candidate = clone(fixture);
  candidate.transitions[0].prefundOrigin = "sponsor";
  assert.equal(validateFiniteLts(candidate).ok, true, "positive sponsor funding is well-formed evidence");
  assert.equal(inspectLts(candidate, "B2").status, "FAIL_COUNTEREXAMPLE", "sponsor funding must fail B2 semantically");
  semanticCases += 1;
}
{
  const candidate = clone(fixture);
  candidate.transitions[1].returnToControl = 1;
  assert.equal(validateFiniteLts(candidate).ok, true, "positive return is a well-formed counterexample");
  assert.equal(inspectLts(candidate, "B4").status, "FAIL_COUNTEREXAMPLE", "positive return must fail B4 semantically");
  semanticCases += 1;
}
{
  const candidate = clone(fixture);
  candidate.transitions[0].buyerPrefund = 104;
  candidate.transitions[0].buyerDebit = 100;
  candidate.transitions[0].debitOrigin = candidate.namedAcquirer;
  candidate.transitions[0].irreversible = false;
  assert.equal(validateFiniteLts(candidate).ok, true, "reversible prefix debit is well formed");
  assert.equal(inspectLts(candidate, "B2").status, "PASS", "reversible prefix debit remains buyer funded");
  assert.equal(inspectLts(candidate, "B3").status, "FAIL_COUNTEREXAMPLE", "reversible prefix debit must fail B3");
  semanticCases += 1;
}
{
  const candidate = clone(fixture);
  candidate.transitions[0].buyerPrefund = 104;
  candidate.transitions[0].buyerDebit = 100;
  candidate.transitions[0].debitOrigin = candidate.namedAcquirer;
  candidate.transitions[0].irreversible = true;
  assert.equal(inspectLts(candidate, "B3").status, "PASS", "irreversible prefix debit may be counted");
  semanticCases += 1;
}

const oneThird = parseExactAmount({ numerator: "1", denominator: "3" });
const oneSixth = parseExactAmount({ numerator: "1", denominator: "6" });
const oneHalf = parseExactAmount({ numerator: "1", denominator: "2" });
const twoFifths = parseExactAmount({ numerator: "2", denominator: "5" });
assert.equal(amountToString(addAmount(oneThird, oneSixth)), "1/2");
assert.equal(compareAmount(twoFifths, oneHalf), -1);
rationalCases += 2;

{
  const candidate = clone(fixture);
  candidate.transitions[0].buyerPrefund = { numerator: "1", denominator: "2" };
  candidate.transitions[1].buyerDebit = { numerator: "1", denominator: "2" };
  assert.equal(validateFiniteLts(candidate).ok, true, "fractional finite LTS must validate exactly");
  assert.equal(amountToString(shortestSuccessfulLtsOutflow(candidate)), "1/2");
  for (const gate of gates) assert.equal(inspectLts(candidate, gate).status, "PASS", `fractional/${gate}: must pass`);
  rationalCases += 1;
}
{
  const huge = { numerator: "900719925474099312345678901234567890", denominator: "1" };
  assert.equal(amountToString(parseExactAmount(huge)), huge.numerator, "BigInt rational must not lose precision");
  rationalCases += 1;
}
{
  assert.equal(amountToString(parseExactAmount(Number.MAX_SAFE_INTEGER)), String(Number.MAX_SAFE_INTEGER));
  const rationalZero = { numerator: "0", denominator: "1" };
  const candidate = clone(fixture);
  candidate.transitions[0].buyerDebit = rationalZero;
  candidate.transitions[0].debitOrigin = "none";
  assert.equal(validateFiniteLts(candidate).ok, true, "canonical rational zero must agree with none origin");
  boundaryCases += 2;
}
{
  const candidate = clone(fixture);
  for (const [prefixIndex, successIndex, terminalDebit] of [[0, 1, 4], [2, 3, 7]]) {
    candidate.transitions[prefixIndex].buyerPrefund = Number.MAX_SAFE_INTEGER;
    candidate.transitions[prefixIndex].buyerDebit = Number.MAX_SAFE_INTEGER;
    candidate.transitions[prefixIndex].debitOrigin = candidate.namedAcquirer;
    candidate.transitions[prefixIndex].irreversible = true;
    candidate.transitions[successIndex].buyerPrefund = terminalDebit;
    candidate.transitions[successIndex].prefundOrigin = candidate.namedAcquirer;
  }
  for (const gate of gates) assert.equal(inspectLts(candidate, gate).status, "PASS", `above-safe-sum/${gate}: must pass`);
  assert.equal(amountToString(shortestSuccessfulLtsOutflow(candidate)), "9007199254740995");
  boundaryCases += 1;
}

console.log("REPORTED_RETURN_FUNDING_OMISSION_REGRESSION=PASS");
console.log(`MALFORMED_SCHEMA_CASES=${malformedCases}`);
console.log(`RAW_JSON_REJECTION_CASES=${rawRejectedCases}`);
console.log(`SEMANTIC_COUNTEREXAMPLE_CASES=${semanticCases}`);
console.log(`EXACT_RATIONAL_CASES=${rationalCases}`);
console.log(`EXACT_BOUNDARY_CASES=${boundaryCases}`);
console.log("FINITE_LTS_V2_NEGATIVE_AND_FRACTION_TESTS=PASS");
