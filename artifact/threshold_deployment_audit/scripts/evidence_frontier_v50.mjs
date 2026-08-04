import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  ZERO,
  addAmount,
  amountToJson,

  compareAmount,
  isZeroAmount,
  minAmount,
  parseJsonRejectingDuplicateKeys,
  requireFiniteLts,
} from "./finite_lts_v2.mjs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(SCRIPT_DIR);
const GATES = ["B1", "B2", "B3", "B4", "B5"];
const SHA256 = /^[0-9a-f]{64}$/;
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function exactKeys(value, allowed, label) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object`);
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${label} has unknown field ${key}`);
}

function resolveInsideRoot(relativePath) {
  if (typeof relativePath !== "string" || relativePath.length === 0 || path.isAbsolute(relativePath)) throw new Error("artifact path must be nonempty and relative");
  const absolute = path.resolve(ROOT, relativePath);
  const prefix = `${path.resolve(ROOT)}${path.sep}`.toLowerCase();
  if (!absolute.toLowerCase().startsWith(prefix)) throw new Error(`artifact path escapes root: ${relativePath}`);
  return absolute;
}

async function readStrict(relativePath, label = relativePath) {
  const absolute = resolveInsideRoot(relativePath);
  const raw = await readFile(absolute);
  return { absolute, raw, value: parseJsonRejectingDuplicateKeys(raw.toString("utf8").replace(/^\uFEFF/, ""), label) };
}

function reachableTransitions(lts) {
  const outgoing = new Map(lts.states.map((state) => [state, []]));
  for (const transition of lts.transitions) outgoing.get(transition.from).push(transition);
  const reachable = new Set([lts.initialState]);
  const queue = [lts.initialState];
  while (queue.length > 0) {
    const state = queue.shift();
    for (const transition of outgoing.get(state)) {
      if (!reachable.has(transition.to)) {
        reachable.add(transition.to);
        queue.push(transition.to);
      }
    }
  }
  return { outgoing, transitions: lts.transitions.filter((transition) => reachable.has(transition.from)) };
}

export function shortestSuccessfulOutflow(lts) {
  const validation = requireFiniteLts(lts);
  const amount = (transition, field) => validation.amounts.get(transition)[field];
  const distances = new Map(lts.states.map((state) => [state, null]));
  distances.set(lts.initialState, ZERO);
  let best = null;
  for (let round = 0; round < lts.states.length; round += 1) {
    let changed = false;
    for (const transition of lts.transitions) {
      const before = distances.get(transition.from);
      if (before === null) continue;
      const candidate = addAmount(before, amount(transition, "buyerDebit"));
      if (transition.success === true) best = best === null ? candidate : minAmount(best, candidate);
      const previous = distances.get(transition.to);
      if (previous === null || compareAmount(candidate, previous) < 0) {
        distances.set(transition.to, candidate);
        changed = true;
      }
    }
    if (!changed) break;
  }
  if (best === null) throw new Error("countermodel has no reachable successful acquisition");
  return best;
}

export function validateCountermodelBinding(record, lts, entry) {
  const expectedEntryKeys = new Set(["recordId", "recordPath", "scopeSha256", "routePhrase", "ltsPath", "ltsSha256"]);
  exactKeys(entry, expectedEntryKeys, `${entry.recordId ?? "entry"} catalog entry`);
  for (const key of expectedEntryKeys) if (!own(entry, key)) throw new Error(`countermodel entry missing ${key}`);
  if (record.schema !== "public-evidence-record/v2" || record.recordType !== "public-deployment") throw new Error(`${entry.recordId}: countermodel requires a public v2 record`);
  if (record.id !== entry.recordId) throw new Error(`${entry.recordId}: record id mismatch`);
  if (!SHA256.test(entry.scopeSha256) || entry.scopeSha256 !== sha256(Buffer.from(canonicalJson(record.scope)))) throw new Error(`${entry.recordId}: scope hash mismatch`);
  if (typeof entry.routePhrase !== "string" || !record.scope.mechanismLanguage.toLowerCase().includes(entry.routePhrase.toLowerCase())) {
    throw new Error(`${entry.recordId}: route phrase is not declared in the mechanism language`);
  }
  if (!record.gates?.B5 || !Array.isArray(record.gates.B5.evidence) || record.gates.B5.evidence.length !== 0) {
    throw new Error(`${entry.recordId}: an admitted B5 object prevents absence-based compatibility`);
  }

  requireFiniteLts(lts);
  if (lts.namedAcquirer !== record.scope.namedAcquirer) throw new Error(`${entry.recordId}: named acquirer mismatch`);
  for (const field of ["asset", "unit", "valuationTime", "conversionLowerPrice", "gasTreatment"]) {
    if (lts.numeraire[field] !== record.scope.numeraire[field]) throw new Error(`${entry.recordId}: numeraire.${field} mismatch`);
  }
  const routeSlug = entry.routePhrase.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  if (lts.states.length !== 2 || lts.transitions.length !== 1) throw new Error(`${entry.recordId}: countermodel must remain a two-state one-transition witness`);
  if (lts.transitions[0].route !== routeSlug) throw new Error(`${entry.recordId}: route slug does not match the scope phrase`);
  if (lts.mappedRoutes.includes(lts.transitions[0].route)) throw new Error(`${entry.recordId}: countermodel route is already mapped`);

  const { outgoing, transitions } = reachableTransitions(lts);
  const successes = transitions.filter((transition) => transition.success === true);
  if (successes.length !== 1 || outgoing.get(successes[0].to).length !== 0) throw new Error(`${entry.recordId}: countermodel success must be unique and terminal`);
  if (successes[0].usableDelivery !== true) throw new Error(`${entry.recordId}: countermodel does not satisfy the pinned usable-delivery predicate`);

  const shortest = shortestSuccessfulOutflow(lts);
  if (!isZeroAmount(shortest)) throw new Error(`${entry.recordId}: countermodel does not have zero named-acquirer outflow`);
  return {
    recordId: record.id,
    routePhrase: entry.routePhrase,
    transitionWitness: successes[0].id,
    states: lts.states.length,
    transitions: lts.transitions.length,
    shortestNamedAcquirerOutflow: amountToJson(shortest),
    b1UsableDelivery: "PASS",
    b5AlternativeRoute: "FAIL_COUNTEREXAMPLE",
    semanticCertificate: 0,
    interpretation: "Exact zero in the admitted public-record compatible-world semantics; not evidence that this route occurs in the physical deployment.",
  };
}

export function solveRepairCatalog(catalog) {
  exactKeys(catalog, new Set(["schema", "claimBoundary", "challenges", "candidateFamilies"]), "repair catalog");
  if (catalog.schema !== "evidence-repair-catalog/v1") throw new Error("wrong repair catalog schema");
  if (!Array.isArray(catalog.challenges) || catalog.challenges.length === 0) throw new Error("repair catalog needs challenges");
  if (!Array.isArray(catalog.candidateFamilies) || catalog.candidateFamilies.length === 0 || catalog.candidateFamilies.length > 24) throw new Error("repair catalog candidate count is invalid");
  const challengeIds = catalog.challenges.map((entry) => entry.id);
  if (new Set(challengeIds).size !== challengeIds.length) throw new Error("duplicate repair challenge id");
  const challengeSet = new Set(challengeIds);
  const familyIds = catalog.candidateFamilies.map((entry) => entry.id);
  if (new Set(familyIds).size !== familyIds.length) throw new Error("duplicate repair family id");
  for (const family of catalog.candidateFamilies) {
    if (!Array.isArray(family.covers) || family.covers.length === 0) throw new Error(`${family.id}: empty coverage`);
    if (new Set(family.covers).size !== family.covers.length) throw new Error(`${family.id}: duplicate coverage`);
    for (const challenge of family.covers) if (!challengeSet.has(challenge)) throw new Error(`${family.id}: unknown challenge ${challenge}`);
  }
  let minimum = Number.POSITIVE_INFINITY;
  const solutions = [];
  for (let mask = 0; mask < (1 << catalog.candidateFamilies.length); mask += 1) {
    const count = mask.toString(2).replaceAll("0", "").length;
    if (count > minimum) continue;
    const covered = new Set();
    const selected = [];
    catalog.candidateFamilies.forEach((family, index) => {
      if ((mask >> index) & 1) {
        selected.push(family.id);
        family.covers.forEach((challenge) => covered.add(challenge));
      }
    });
    if (covered.size !== challengeSet.size) continue;
    if (count < minimum) {
      minimum = count;
      solutions.length = 0;
    }
    solutions.push(selected);
  }
  if (!Number.isFinite(minimum)) throw new Error("repair catalog cannot cover all challenges");
  return { challengeCount: challengeIds.length, candidateFamilyCount: familyIds.length, minimumFamilyCount: minimum, minimumSolutions: solutions };
}

async function verifySourceCorpus() {
  const { value } = await readStrict("results/raw_capture_integrity.v48.json", "raw capture integrity result");
  if (value.schema !== "raw-public-capture-integrity/v48") throw new Error("wrong raw-capture result schema");
  const groups = [["officialFiles", value.officialFiles], ["apiFiles", value.apiFiles], ["rpcFiles", value.rpcFiles]];
  let files = 0;
  let bytes = 0;
  for (const [group, entries] of groups) {
    if (!Array.isArray(entries)) throw new Error(`raw capture ${group} missing`);
    for (const entry of entries) {
      const actual = await readFile(resolveInsideRoot(entry.path));
      if (sha256(actual) !== entry.sha256) throw new Error(`${entry.path}: raw corpus hash mismatch`);
      files += 1;
      bytes += actual.length;
    }
  }
  return {
    officialFiles: value.officialFiles.length,
    apiFiles: value.apiFiles.length,
    rpcFiles: value.rpcFiles.length,
    totalFilesRehashed: files,
    totalBytesRehashed: bytes,
    exactEarlierFreezeDigestMatches: value.summary.exactFrozenDigestMatches,
    admittedBridgeProofObjects: 0,
    interpretation: "These files establish context and identifiers; none is admitted by the frozen records as a B1--B5 proof object.",
  };
}

export async function evaluateFrontier() {
  const countermodelInput = await readStrict("data/countermodel_catalog.v1.json", "countermodel catalog");
  const catalog = countermodelInput.value;
  exactKeys(catalog, new Set(["schema", "claimBoundary", "entries"]), "countermodel catalog");
  if (catalog.schema !== "scope-bound-compatible-countermodel-catalog/v1" || !Array.isArray(catalog.entries)) throw new Error("wrong countermodel catalog schema");
  if (catalog.entries.length !== 4) throw new Error("countermodel catalog must match the four-record cohort");
  const ids = catalog.entries.map((entry) => entry.recordId);
  if (new Set(ids).size !== ids.length) throw new Error("duplicate countermodel record id");

  const countermodels = [];
  let gateCellsScreened = 0;
  let admittedGateEvidenceObjects = 0;
  for (const entry of catalog.entries) {
    if (!SHA256.test(entry.ltsSha256)) throw new Error(`${entry.recordId}: malformed LTS hash`);
    const recordInput = await readStrict(entry.recordPath, `${entry.recordId} record`);
    const ltsInput = await readStrict(entry.ltsPath, `${entry.recordId} countermodel`);
    if (sha256(ltsInput.raw) !== entry.ltsSha256) throw new Error(`${entry.recordId}: countermodel file hash mismatch`);
    for (const gate of GATES) {
      if (!recordInput.value.gates?.[gate] || !Array.isArray(recordInput.value.gates[gate].evidence)) throw new Error(`${entry.recordId}/${gate}: malformed gate evidence list`);
      gateCellsScreened += 1;
      admittedGateEvidenceObjects += recordInput.value.gates[gate].evidence.length;
    }
    countermodels.push({
      ...validateCountermodelBinding(recordInput.value, ltsInput.value, entry),
      recordSha256: sha256(recordInput.raw),
      scopeSha256: entry.scopeSha256,
      countermodelLtsSha256: entry.ltsSha256,
    });
  }
  if (gateCellsScreened !== 20 || admittedGateEvidenceObjects !== 0) throw new Error("public gate-screening baseline changed");

  const sourceCorpus = await verifySourceCorpus();
  const repairInput = await readStrict("data/repair_catalog.v1.json", "repair catalog");
  const repair = solveRepairCatalog(repairInput.value);
  if (repair.minimumFamilyCount !== 3) throw new Error("catalog-relative repair frontier changed");
  return {
    schema: "scope-bound-countermodel-frontier-result/v1",
    countermodelCatalogSha256: sha256(countermodelInput.raw),
    repairCatalogSha256: sha256(repairInput.raw),
    sourceCorpus,
    publicRecords: countermodels.length,
    gateCellsScreened,
    admittedGateEvidenceObjects,
    exactZeroCompatibleCountermodels: countermodels.length,
    countermodels,
    repairFrontier: {
      ...repair,
      observedCandidateFamiliesInPublicRecords: 0,
      unresolvedChallengeClassesPerPublicRecord: repair.challengeCount,
      interpretation: "The count is relative to the declared candidate-family catalog. It is not a time, money, or proof-construction estimate.",
    },
    claimBoundary: "The countermodels prove exact zero only in the admitted public-record compatible-world semantics. They do not allege an implemented route, insecurity, or population prevalence; eliminating them requires new evidence or a narrower proved mechanism language.",
  };
}

async function main() {
  const result = await evaluateFrontier();
  const bytes = Buffer.from(`${JSON.stringify(result, null, 2)}\n`);
  const generatedPath = path.join(ROOT, "results", "evidence_frontier.generated.json");
  const canonicalPath = path.join(ROOT, "results", "evidence_frontier.v1.json");
  await writeFile(generatedPath, bytes);
  if (process.argv.includes("--write-canonical")) await writeFile(canonicalPath, bytes);
  else {
    const canonical = await readFile(canonicalPath);
    if (!canonical.equals(bytes)) throw new Error(`generated/canonical frontier mismatch: ${sha256(bytes)} != ${sha256(canonical)}`);
  }
  console.log(`SOURCE_FILES_REHASHED=${result.sourceCorpus.totalFilesRehashed}`);
  console.log(`PUBLIC_GATE_CELLS_SCREENED=${result.gateCellsScreened}`);
  console.log(`ADMITTED_PUBLIC_GATE_PROOF_OBJECTS=${result.admittedGateEvidenceObjects}`);
  console.log(`EXACT_ZERO_COMPATIBLE_COUNTERMODELS=${result.exactZeroCompatibleCountermodels}`);
  console.log(`REPAIR_CHALLENGES=${result.repairFrontier.challengeCount}`);
  console.log(`CATALOG_RELATIVE_MINIMUM_REPAIR_FAMILIES=${result.repairFrontier.minimumFamilyCount}`);
  console.log(`FRONTIER_CANONICAL_SHA256=${sha256(bytes)}`);
  console.log("SCOPE_BOUND_COUNTERMODEL_FRONTIER=PASS");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}
