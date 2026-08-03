import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const EVALUATOR_PATH = fileURLToPath(import.meta.url);
const SCRIPT_DIR = path.dirname(EVALUATOR_PATH);
const ROOT = path.dirname(SCRIPT_DIR);
const RECORD_DIR = path.join(ROOT, "data", "records_v48");
const POLICY_PATH = path.join(ROOT, "policy.public-evidence.v2.json");
const GENERATED_PATH = path.join(ROOT, "results", "bridge_audit.generated.json");
const CANONICAL_PATH = path.join(ROOT, "results", "bridge_audit.v2.json");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const parse = (bytes, label) => {
  try { return JSON.parse(bytes.toString("utf8").replace(/^\uFEFF/, "")); }
  catch (error) { throw new Error(`${label}: invalid JSON: ${error.message}`); }
};
const stable = (value) => `${JSON.stringify(value, null, 2)}\n`;
const isAmount = (value) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const isInside = (base, target) => {
  const rel = path.relative(base, target);
  return rel === "" || (!rel.startsWith(`..${path.sep}`) && rel !== ".." && !path.isAbsolute(rel));
};
const pointerGet = (value, pointer) => {
  if (pointer === "") return value;
  if (!pointer.startsWith("/")) throw new Error(`bad JSON pointer ${pointer}`);
  return pointer.slice(1).split("/").reduce((node, token) => {
    const key = token.replace(/~1/g, "/").replace(/~0/g, "~");
    if (node === null || typeof node !== "object" || !(key in node)) throw new Error(`missing JSON pointer ${pointer}`);
    return node[key];
  }, value);
};

const evaluatorBytes = await readFile(EVALUATOR_PATH);
const policyBytes = await readFile(POLICY_PATH);
const policy = parse(policyBytes, POLICY_PATH);
const gateIds = policy.bridgeGates.map((gate) => gate.id);
if (new Set(gateIds).size !== gateIds.length || gateIds.length === 0) throw new Error("invalid gate policy");
for (const status of ["PASS", "FAIL_CLOSED_MISSING_EVIDENCE", "FAIL_COUNTEREXAMPLE", "UNKNOWN", "NOT_APPLICABLE"]) {
  if (!policy.primitiveStatuses.includes(status)) throw new Error(`policy omits ${status}`);
}

const recordNames = (await readdir(RECORD_DIR)).filter((name) => name.endsWith(".json")).sort();
if (recordNames.length === 0) throw new Error("no evidence records");
const records = [];
for (const name of recordNames) {
  const filePath = path.join(RECORD_DIR, name);
  const bytes = await readFile(filePath);
  const value = parse(bytes, filePath);
  records.push({ filePath, relativePath: path.relative(ROOT, filePath).replaceAll("\\", "/"), bytes, value });
}
if (new Set(records.map(({ value }) => value.id)).size !== records.length) throw new Error("duplicate record id");

const sourceCache = new Map();
async function verifySourceRef(recordPath, ref) {
  for (const key of ["id", "path", "sha256", "pointer"]) if (!(key in ref)) throw new Error(`source reference missing ${key}`);
  const absolute = path.resolve(path.dirname(recordPath), ref.path);
  if (!isInside(ROOT, absolute)) throw new Error(`source escapes audit root: ${ref.path}`);
  let cached = sourceCache.get(absolute);
  if (!cached) {
    const bytes = await readFile(absolute);
    const actualSha256 = sha(bytes);
    let json = null;
    if (absolute.endsWith(".json")) json = parse(bytes, absolute);
    cached = { bytes, actualSha256, json };
    sourceCache.set(absolute, cached);
  }
  if (cached.actualSha256 !== ref.sha256.toLowerCase()) throw new Error(`${ref.path}: source hash mismatch`);
  let pointerValueHash = null;
  if (cached.json !== null) pointerValueHash = sha(Buffer.from(JSON.stringify(pointerGet(cached.json, ref.pointer))));
  else if (ref.pointer !== "") throw new Error(`${ref.path}: non-JSON source cannot use pointer`);
  return {
    id: ref.id,
    path: path.relative(ROOT, absolute).replaceAll("\\", "/"),
    sourceSha256: cached.actualSha256,
    pointer: ref.pointer,
    pointerValueSha256: pointerValueHash,
    value: cached.json === null ? null : pointerGet(cached.json, ref.pointer),
  };
}

function inspectLts(lts, gate) {
  const fail = (detail, witness = null) => ({ status: "FAIL_COUNTEREXAMPLE", detail, witness });
  const unknown = (detail) => ({ status: "UNKNOWN", detail, witness: null });
  if (lts?.schema !== "finite-acquisition-lts/v1" || !Array.isArray(lts.states) || !Array.isArray(lts.transitions)) return unknown("malformed finite LTS");
  if (!lts.states.includes(lts.initialState) || new Set(lts.states).size !== lts.states.length) return unknown("invalid state set or initial state");
  const mapped = new Set(lts.mappedRoutes ?? []);
  const outgoing = new Map(lts.states.map((state) => [state, []]));
  for (const transition of lts.transitions) {
    if (!outgoing.has(transition.from) || !outgoing.has(transition.to)) return unknown(`transition ${transition.id ?? "?"} has an unknown endpoint`);
    for (const field of ["buyerDebit", "buyerPrefund", "returnToControl", "externalFunding"]) {
      const amount = transition[field] ?? 0;
      if (!isAmount(amount)) return unknown(`transition ${transition.id ?? "?"} has invalid or inexact ${field}`);
    }
    outgoing.get(transition.from).push(transition);
  }
  const reachable = new Set([lts.initialState]);
  const queue = [lts.initialState];
  while (queue.length) {
    const state = queue.shift();
    for (const transition of outgoing.get(state)) if (!reachable.has(transition.to)) { reachable.add(transition.to); queue.push(transition.to); }
  }
  const transitions = lts.transitions.filter((transition) => reachable.has(transition.from));
  const successes = transitions.filter((transition) => transition.success === true);
  const nonterminalSuccess = successes.find((transition) => outgoing.get(transition.to).length > 0);
  if (nonterminalSuccess) return unknown(`success ${nonterminalSuccess.id ?? "?"} does not end at the accounting-window terminal`);
  if (successes.length === 0) return { status: "NOT_APPLICABLE", detail: "the exact finite LTS has no reachable successful acquisition", witness: null };
  if (gate === "B1") {
    const witness = successes.find((transition) => transition.usableDelivery !== true);
    return witness ? fail("reachable success lacks usable delivery", witness.id) : { status: "PASS", detail: `${successes.length} reachable success transition(s) satisfy the pinned usable-delivery predicate`, witness: null };
  }
  if (gate === "B2") {
    const badOrigin = transitions.find((transition) => Number(transition.buyerDebit ?? 0) > 0 && transition.debitOrigin !== lts.namedAcquirer);
    if (badOrigin) return fail("positive debit is not bound to the named acquirer", badOrigin.id);
    const badPrefund = transitions.find((transition) => Number(transition.buyerPrefund ?? 0) > 0 && transition.prefundOrigin !== lts.namedAcquirer);
    if (badPrefund) return fail("positive prefund is not bound to the named acquirer", badPrefund.id);
    const minBalance = new Map(lts.states.map((state) => [state, Number.POSITIVE_INFINITY]));
    minBalance.set(lts.initialState, 0);
    for (let round = 0; round < lts.states.length; round += 1) {
      let changed = false;
      for (const transition of transitions) {
        const before = minBalance.get(transition.from);
        if (!Number.isFinite(before)) continue;
        const prefund = transition.buyerPrefund ?? 0;
        const debit = transition.buyerDebit ?? 0;
        const available = before + prefund;
        if (!Number.isSafeInteger(available)) return unknown("prefunding path sum exceeds exact safe-integer arithmetic");
        if (debit > available) return fail("a reachable debit path lacks named-acquirer prefunding", transition.id);
        const after = available - debit;
        if (after < minBalance.get(transition.to)) { minBalance.set(transition.to, after); changed = true; }
      }
      if (!changed) break;
      if (round === lts.states.length - 1) return unknown("prefunding reachability contains a decreasing cycle");
    }
    return { status: "PASS", detail: "every reachable debit path is funded from the named acquirer", witness: null };
  }
  if (gate === "B3") {
    const bad = successes.find((transition) => mapped.has(transition.route) && (transition.usableDelivery !== true || Number(transition.buyerDebit ?? 0) <= 0 || transition.irreversible !== true));
    return bad ? fail("mapped usable success is not atomic with an irreversible positive debit", bad.id) : { status: "PASS", detail: "every mapped usable success is atomic with an irreversible positive debit", witness: null };
  }
  if (gate === "B4") {
    const mappedSuccesses = successes.filter((transition) => mapped.has(transition.route));
    const reverse = new Map(lts.states.map((state) => [state, []]));
    for (const transition of transitions) reverse.get(transition.to).push(transition.from);
    const canReachMappedSuccess = new Set(mappedSuccesses.map((transition) => transition.from));
    const pending = [...canReachMappedSuccess];
    while (pending.length) {
      const state = pending.shift();
      for (const predecessor of reverse.get(state)) if (!canReachMappedSuccess.has(predecessor)) { canReachMappedSuccess.add(predecessor); pending.push(predecessor); }
    }
    const relevant = transitions.filter((transition) => mappedSuccesses.includes(transition) || canReachMappedSuccess.has(transition.to));
    const bad = relevant.find((transition) => Number(transition.returnToControl ?? 0) > 0 || Number(transition.externalFunding ?? 0) > 0);
    return bad ? fail("a mapped-success prefix contains an unclosed return or external-funding edge", bad.id) : { status: "PASS", detail: "every mapped-success prefix closes return-to-control and external-funding edges", witness: null };
  }
  if (gate === "B5") {
    const bad = successes.find((transition) => transition.usableDelivery === true && !mapped.has(transition.route));
    return bad ? fail("usable success exists outside the mapped payment-preserving route set", bad.id) : { status: "PASS", detail: "every reachable usable success is in the mapped route set", witness: null };
  }
  return unknown(`unsupported gate ${gate}`);
}

function shortestSuccessfulLtsOutflow(lts) {
  if (lts?.schema !== "finite-acquisition-lts/v1" || !Array.isArray(lts.states) || !Array.isArray(lts.transitions)) {
    throw new Error("cannot compute a certificate from a malformed finite LTS");
  }
  if (!lts.states.includes(lts.initialState) || new Set(lts.states).size !== lts.states.length) {
    throw new Error("cannot compute a certificate from an invalid finite LTS state set");
  }
  const distances = new Map(lts.states.map((state) => [state, Number.POSITIVE_INFINITY]));
  distances.set(lts.initialState, 0);
  let best = Number.POSITIVE_INFINITY;
  for (let round = 0; round < lts.states.length; round += 1) {
    let changed = false;
    for (const transition of lts.transitions) {
      if (!distances.has(transition.from) || !distances.has(transition.to)) throw new Error(`transition ${transition.id ?? "?"} has an unknown endpoint`);
      const weight = transition.buyerDebit ?? 0;
      if (!isAmount(weight)) throw new Error(`transition ${transition.id ?? "?"} has an invalid or inexact buyer debit`);
      const before = distances.get(transition.from);
      if (!Number.isFinite(before)) continue;
      const candidate = before + weight;
      if (!Number.isSafeInteger(candidate)) throw new Error("path sum exceeds exact safe-integer arithmetic");
      if (transition.success === true) best = Math.min(best, candidate);
      if (candidate < distances.get(transition.to)) {
        distances.set(transition.to, candidate);
        changed = true;
      }
    }
    if (!changed) break;
  }
  if (!Number.isFinite(best)) throw new Error("admitted finite LTS has no reachable successful acquisition");
  return best;
}

function combineGate(evidenceResults) {
  if (evidenceResults.some((result) => result.status === "FAIL_COUNTEREXAMPLE")) return "FAIL_COUNTEREXAMPLE";
  if (evidenceResults.length === 0) return "FAIL_CLOSED_MISSING_EVIDENCE";
  if (evidenceResults.some((result) => result.status === "UNKNOWN")) return "UNKNOWN";
  if (evidenceResults.every((result) => result.status === "NOT_APPLICABLE")) return "NOT_APPLICABLE";
  if (evidenceResults.every((result) => result.status === "PASS" || result.status === "NOT_APPLICABLE")) return "PASS";
  return "UNKNOWN";
}
function combineRecord(gates) {
  const statuses = Object.values(gates).map((gate) => gate.status);
  for (const candidate of policy.decisionPrecedence) if (statuses.includes(candidate)) return candidate;
  return "UNKNOWN";
}

const compiled = [];
for (const record of records) {
  const value = record.value;
  if (value.schema !== "public-evidence-record/v2") throw new Error(`${record.relativePath}: wrong schema`);
  for (const field of policy.claimScopeRequired) if (!(field in value.scope) || value.scope[field] === null || value.scope[field] === "") throw new Error(`${value.id}: incomplete claim scope ${field}`);
  for (const field of policy.numeraireRequired) if (!(field in value.scope.numeraire) || value.scope.numeraire[field] === "") throw new Error(`${value.id}: incomplete numeraire ${field}`);
  const verifiedRefs = new Map();
  for (const ref of value.sourceRefs) {
    if (verifiedRefs.has(ref.id)) throw new Error(`${value.id}: duplicate source ref ${ref.id}`);
    verifiedRefs.set(ref.id, await verifySourceRef(record.filePath, ref));
  }
  const gates = {};
  for (const gate of gateIds) {
    const input = value.gates[gate];
    if (!input) throw new Error(`${value.id}: missing gate record ${gate}`);
    if ("missingPredicates" in input) throw new Error(`${value.id}/${gate}: verdict-like missingPredicates input is forbidden`);
    if (!Array.isArray(input.contextRefs) || !Array.isArray(input.evidence)) throw new Error(`${value.id}/${gate}: malformed context or evidence list`);
    const context = input.contextRefs.map((id) => {
      if (!verifiedRefs.has(id)) throw new Error(`${value.id}/${gate}: unknown context ref ${id}`);
      const ref = verifiedRefs.get(id);
      return { id: ref.id, path: ref.path, sourceSha256: ref.sourceSha256, pointer: ref.pointer, pointerValueSha256: ref.pointerValueSha256 };
    });
    const evidenceResults = [];
    for (const evidence of input.evidence) {
      const ref = verifiedRefs.get(evidence.sourceRef);
      if (!ref) throw new Error(`${value.id}/${gate}: unknown evidence ref ${evidence.sourceRef}`);
      if (evidence.type === "finite_lts_gate") {
        if (evidence.gate !== gate) throw new Error(`${value.id}/${gate}: finite LTS evidence is tagged for ${evidence.gate}`);
        if (ref.value?.namedAcquirer !== value.scope.namedAcquirer) throw new Error(`${value.id}/${gate}: LTS named acquirer differs from the claim scope`);
        if (JSON.stringify(ref.value?.numeraire) !== JSON.stringify(value.scope.numeraire)) throw new Error(`${value.id}/${gate}: LTS numeraire differs from the claim scope`);
        evidenceResults.push({ type: evidence.type, sourceRef: evidence.sourceRef, ...inspectLts(ref.value, gate) });
      } else evidenceResults.push({ type: evidence.type, sourceRef: evidence.sourceRef, status: "UNKNOWN", detail: "unsupported evidence-check type", witness: null });
    }
    const gatePolicy = policy.bridgeGates.find((entry) => entry.id === gate);
    const missingPredicates = evidenceResults.length === 0 ? [`${gate}: required ${gatePolicy.name} proof object`] : [];
    gates[gate] = { status: combineGate(evidenceResults), missingPredicates, context, evidenceResults };
  }
  const status = combineRecord(gates);
  const ltsSourceRefs = [...new Set(gateIds.flatMap((gate) => value.gates[gate].evidence)
    .filter((evidence) => evidence.type === "finite_lts_gate")
    .map((evidence) => evidence.sourceRef))];
  let certificate = 0;
  let certificateDerivation = { type: "fail-closed-zero", sourceRef: null, value: 0 };
  if (status === "PASS") {
    if (ltsSourceRefs.length !== 1) throw new Error(`${value.id}: a positive certificate requires exactly one admitted finite LTS`);
    const sourceRef = ltsSourceRefs[0];
    certificate = shortestSuccessfulLtsOutflow(verifiedRefs.get(sourceRef).value);
    if (!(certificate > 0)) throw new Error(`${value.id}: admitted finite LTS has no positive shortest successful outflow`);

    certificateDerivation = { type: "shortest-successful-path", sourceRef, value: certificate };
  }
  compiled.push({
    id: value.id,
    recordType: value.recordType,
    recordPath: record.relativePath,
    recordSha256: sha(record.bytes),
    scope: value.scope,
    gates,
    status,
    certifiedNamedAcquirerNetIrreversibleOutflow: certificate,
    certificateDerivation,
    claimBoundary: value.claimBoundary,
    interpretation: certificate === 0 ? policy.zeroInterpretation : "Positive only in the exact typed scope and mechanism language above."
  });
}
compiled.sort((a, b) => a.id.localeCompare(b.id));
const invalidAmounts = [-1, 1.5, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1, "1", null];
if (![0, 1, Number.MAX_SAFE_INTEGER].every(isAmount) || invalidAmounts.some(isAmount)) throw new Error("safe-integer amount predicate self-test failed");
const overflowLts = {
  schema: "finite-acquisition-lts/v1", states: ["s0", "s1", "s2"], initialState: "s0",
  transitions: [
    { id: "large", from: "s0", to: "s1", buyerDebit: Number.MAX_SAFE_INTEGER - 1 },
    { id: "overflow", from: "s1", to: "s2", buyerDebit: 2, success: true }
  ]
};
let rejectedOverflow = false;
try { shortestSuccessfulLtsOutflow(overflowLts); } catch (error) { rejectedOverflow = error.message.includes("exceeds exact safe-integer arithmetic"); }
if (!rejectedOverflow) throw new Error("unsafe path-sum overflow was not rejected");
const publicRecords = compiled.filter((record) => record.recordType === "public-deployment");
const result = {
  schema: "public-evidence-compiler-result/v2",
  generatedFrom: {
    evaluatorPath: path.relative(ROOT, EVALUATOR_PATH).replaceAll("\\", "/"),
    evaluatorSha256: sha(evaluatorBytes),
    policyPath: path.relative(ROOT, POLICY_PATH).replaceAll("\\", "/"),
    policySha256: sha(policyBytes),
    recordSetSha256: sha(Buffer.from(records.map((record) => `${record.relativePath}:${sha(record.bytes)}`).sort().join("\n")))
  },
  statusVocabulary: policy.primitiveStatuses,
  publicDeploymentCount: publicRecords.length,
  constructedDiagnosticCount: compiled.length - publicRecords.length,
  positivePublicDeploymentCertificates: publicRecords.filter((record) => record.certifiedNamedAcquirerNetIrreversibleOutflow > 0).length,
  auditQuestion: "What named-acquirer net irreversible outflow follows from the admitted typed evidence; not whether any project claimed such a bound.",
  resultBoundary: "Fixed author-selected public cohort plus separately labelled constructed diagnostics; no prevalence, insecurity, independent preregistration, fiat-value, or buyer-bound cryptographic-delivery claim.",
  records: compiled
};
await mkdir(path.dirname(GENERATED_PATH), { recursive: true });
const output = stable(result);
await writeFile(GENERATED_PATH, output, "utf8");
if (process.argv.includes("--freeze")) await writeFile(CANONICAL_PATH, output, "utf8");
console.log(`PUBLIC_DEPLOYMENTS=${result.publicDeploymentCount}`);
console.log(`CONSTRUCTED_DIAGNOSTICS=${result.constructedDiagnosticCount}`);
console.log(`POSITIVE_PUBLIC_CERTIFICATES=${result.positivePublicDeploymentCertificates}`);
console.log("EXACT_SAFE_INTEGER_AMOUNT_ARITHMETIC=PASS");
console.log("DATA_DRIVEN_EVIDENCE_COMPILER=PASS");