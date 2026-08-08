import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const root = path.dirname(fileURLToPath(import.meta.url));
const executionZip = path.join(root, "frozen", "two_host_execution_evidence.public.zip");
const fidelityZip = path.join(root, "frozen", "code_fidelity_evidence.zip");

const EXECUTION_SHA256 =
  "f3be587c4586a193ba1f2515f7f5c612b11162e80b42253bc30496976f25e65e";
const FIDELITY_SHA256 =
  "8b5dff61e3cde30402eeda19869626d721b6910135afa5221dba91dade95f71e";
const CODE_MANIFEST_SHA256 =
  "b1a84b542b752e4686f164aecf856167ffe5391fb778267d0cff0a5e551ad468";
const CANONICAL_SHA256 =
  "4000b777402fe4d2435287c69a4eb6c7c6e2cc84df64088162750ddcc7f22478";
const SOURCE_KERNEL_SHA256 =
  "6f1327541769d77f2a60d7c331c933682879a50912cbb457f8ef9d640d82406c";
const END_TO_END_SHA256 =
  "58950527a202d0bf55324b05e7803073f063e0df25daa346d45acbf1283396c9";

const failures = [];
function check(name, condition, detail = "") {
  if (!condition) failures.push(detail ? `${name}: ${detail}` : name);
}
function allTrue(value) {
  return value && Object.values(value).length > 0 && Object.values(value).every((item) => item === true);
}
function lower(value) {
  return String(value ?? "").trim().toLowerCase();
}
function entryHash(entries, name) {
  const data = entries.get(name);
  if (!data) throw new Error(`missing archive entry: ${name}`);
  return sha256(data);
}

function sha256(data) {
  return createHash("sha256").update(data).digest("hex");
}

function sha256File(file) {
  return sha256(fs.readFileSync(file));
}

function readZipEntries(file) {
  const buf = fs.readFileSync(file);
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error(`zip end-of-central-directory not found: ${file}`);

  const count = buf.readUInt16LE(eocd + 10);
  let offset = buf.readUInt32LE(eocd + 16);
  const entries = new Map();
  for (let i = 0; i < count; i++) {
    if (buf.readUInt32LE(offset) !== 0x02014b50) throw new Error("bad central directory header");
    const method = buf.readUInt16LE(offset + 10);
    const compressedSize = buf.readUInt32LE(offset + 20);
    const nameLength = buf.readUInt16LE(offset + 28);
    const extraLength = buf.readUInt16LE(offset + 30);
    const commentLength = buf.readUInt16LE(offset + 32);
    const localOffset = buf.readUInt32LE(offset + 42);
    const name = buf.toString("utf8", offset + 46, offset + 46 + nameLength).replace(/\\/g, "/");
    offset += 46 + nameLength + extraLength + commentLength;
    if (name.endsWith("/")) continue;

    const localNameLength = buf.readUInt16LE(localOffset + 26);
    const localExtraLength = buf.readUInt16LE(localOffset + 28);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    const raw = buf.subarray(dataStart, dataStart + compressedSize);
    const data = method === 0 ? raw : method === 8 ? zlib.inflateRawSync(raw) : null;
    if (data === null) throw new Error(`unsupported ZIP compression method ${method}: ${name}`);
    entries.set(name, data);
  }
  return entries;
}

function json(entries, name) {
  const data = entries.get(name);
  if (!data) throw new Error(`missing archive entry: ${name}`);
  return JSON.parse(data.toString("utf8"));
}

check("execution package digest", sha256File(executionZip) === EXECUTION_SHA256);
check("code-fidelity package digest", sha256File(fidelityZip) === FIDELITY_SHA256);

const execution = readZipEntries(executionZip);
check("public execution entry count", execution.size === 73, String(execution.size));
const forbiddenName =
  /(^|\/)(private_metadata|secrets?|__pycache__)(\/|$)|\.pyc$|\.nonces?\.log$|\.before-|\.zip$/i;
const forbiddenEntries = [...execution.keys()].filter((name) => forbiddenName.test(name));
check("public package has no private or nested-archive entries", forbiddenEntries.length === 0, forbiddenEntries.join(", "));
for (const [name, data] of execution) {
  if (!/\.(json|txt|md|py|ps1|sha256)$/i.test(name)) continue;
  const text = data.toString("utf8");
  check(`no private LAN address in ${name}`, !/\b192\.168\.\d{1,3}\.\d{1,3}\b/.test(text));
  check(`no Windows user path in ${name}`, !/[A-Za-z]:\\Users\\/i.test(text));
}

const manifestText = execution.get("MANIFEST.sha256")?.toString("utf8") ?? "";
const manifest = new Map(
  manifestText.trimEnd().split("\n").filter(Boolean).map((line) => {
    const match = line.match(/^([0-9a-fA-F]{64})  (.+)$/);
    return match ? [match[2], match[1].toLowerCase()] : [`<malformed:${line}>`, "MALFORMED"];
  }),
);
check("public manifest covers every payload", manifest.size === execution.size - 1);
for (const [name, digest] of manifest) {
  check(`manifest entry ${name}`, execution.has(name) && sha256(execution.get(name)) === digest);
}

const release = json(execution, "PUBLIC_RELEASE.json");
check("public-release schema", release.schema === "ptr-two-host-public-release/v5");
check("public-release status", release.status === "PASS");
check("release code-manifest binding", lower(release.code_manifest_sha256) === CODE_MANIFEST_SHA256);
check("release source binding", lower(release.source_coverage_result_sha256) === SOURCE_KERNEL_SHA256);
check("release end-to-end binding", lower(release.end_to_end_certificate_sha256) === END_TO_END_SHA256);

const canonical = json(execution, "results/canonical_result.v3.json");
const q = canonical.quantities;
const catalog = canonical.route_catalog;
check("canonical schema", canonical.schema === "paid-threshold-response-two-host/v5");
check("canonical frozen digest", entryHash(execution, "results/canonical_result.v3.json") === CANONICAL_SHA256);
check("canonical checks", allTrue(canonical.checks));
check("run passed", canonical.run_passed === true && canonical.failed_checks.length === 0);
check("theory cover is 10", q.theory_cover === 10);
check("baseline execution floor is 10", q.baseline_execution_floor === 10);
check("catalog certificate is 10", q.catalog_certificate === 10);
check("observed minimum is 10", q.observed_minimum === 10);
check("remote-only coalition floors at 19", q.remote_only_execution_floor === 19);
check("expensive coalition floors at 22", q.expensive_execution_floor === 22);
check("840 routes enumerated", catalog.routes_enumerated === 840 && catalog.eligible_routes === 840 && catalog.entries.length === 840);
check("every route certified", catalog.entries.every((row) => row.catalog_eligible === true && row.status === "CERTIFIED"));
check("route catalog is complete", catalog.catalog_complete === true && catalog.incomplete_routes === 0);
check("all route floors are ledger-derived", catalog.all_floors_ledger_derived === true);
check("24 minimizing routes", catalog.minimizing_routes === 24);
check("two-host run class", canonical.scope.run_class === "CERTIFIED_TWO_HOST");
check("two-host separation", canonical.scope.host_separation_status === "PASS");
check("key isolation", canonical.scope.key_isolation_status === "PASS");
check("finite-language scope", canonical.scope.deployment_wide === false);

const outage = json(execution, "results/outage_result.v3.json");
check("outage schema", outage.schema === "paid-threshold-response-two-host-outage/v5");
check("outage fails closed", allTrue(outage.checks));
const recovery = json(execution, "results/recovery_result.v3.json");
check("recovery schema", recovery.schema === "paid-threshold-response-two-host-outage/v5");
check("recovery succeeds", allTrue(recovery.checks));

const capability = json(execution, "results/capability_certificate.v3.json");
check("capability schema", capability.schema === "paid-threshold-response-two-host-capability/v5");
check("capability checks", allTrue(capability.checks));
check(
  "capability baseline",
  capability.baseline.status === "CERTIFIED" && capability.baseline.circuit_value === 10,
);
check("potential verified", capability.baseline.potential_verified === true);
check("free bypass refuted", capability.bypass_fixture.status === "REFUTED_BY_DERIVATION");
check("shared debit withheld", capability.shared_debit_fixture.status === "NONDECOMPOSABLE");
check(
  "route compression",
  capability.route_compression.ordered_routes === 840 &&
    capability.route_compression.coalition_derivations === 35 &&
    capability.route_compression.threshold_nodes === 1,
);

const coverage = json(execution, "results/coverage_certificate.v3.json");
check("coverage schema", coverage.schema === "paid-threshold-response-two-host-coverage/v5");
check("sealed composition baseline", coverage.baseline.status === "SEALED" && allTrue(coverage.checks));
check("LC0-LC7 coverage mutations caught", Object.values(coverage.mutations).length === 9 && Object.values(coverage.mutations).every((row) => row.status === "COVERAGE_NOT_ESTABLISHED" && row.isolates_expected_condition === true));

const source = json(execution, "results/source_coverage_kernel.v1.json");
check("source-kernel frozen digest", entryHash(execution, "results/source_coverage_kernel.v1.json") === SOURCE_KERNEL_SHA256);
check("source-kernel pass", source.schema === "ptr-source-coverage-kernel/v1" && source.status === "PASS" && allTrue(source.checks));
for (const obligation of ["LC1_SOURCE_PRODUCER_COMPLETENESS", "LC3_SOURCE_SECRET_CONFINEMENT", "LC5_SOURCE_LIFECYCLE_CLOSURE", "LC7_SOURCE_DELIVERY_ROOT"]) {
  check(`${obligation} discharged`, source.obligations[obligation].status === "PASS");
}
const sourceMutations = json(execution, "results/source_coverage_mutation_matrix.v1.json");
check("14 source mutations caught", sourceMutations.status === "PASS" && sourceMutations.mutations_caught === 14 && sourceMutations.mutations_total === 14);

const manifestId = lower(execution.get("project/config/code_manifest.v1.sha256")?.toString("utf8"));
const manifestJsonDigest = entryHash(execution, "project/config/code_manifest.v1.json");
check("archived code-manifest identity", manifestId === CODE_MANIFEST_SHA256);
const codeManifest = json(execution, "project/config/code_manifest.v1.json");
check("code-manifest schema", codeManifest.schema === "ptr-code-manifest-fidelity/v1");
check("52 pinned files", Object.keys(codeManifest.files).length === 52);
for (const [name, digest] of Object.entries(codeManifest.files)) {
  check(`archived pinned file ${name}`, entryHash(execution, `project/${name}`) === lower(digest));
}

const archivedBinding = json(execution, "results/code_manifest_binding.v1.json");
const archivedMutations = json(execution, "results/code_manifest_mutation_matrix.v1.json");
check("archived code fidelity", archivedBinding.status === "PASS" && allTrue(archivedBinding.checks) && lower(archivedBinding.manifest_sha256) === manifestId);
check("archived code mutations", archivedMutations.status === "PASS" && archivedMutations.caught === 6 && archivedMutations.total === 6 && lower(archivedMutations.baseline_manifest_sha256) === manifestId);

const endToEnd = json(execution, "results/end_to_end_certificate.v1.json");
check("end-to-end frozen digest", entryHash(execution, "results/end_to_end_certificate.v1.json") === END_TO_END_SHA256);
check("end-to-end pass", endToEnd.schema === "ptr-end-to-end-finite-language-certificate/v1" && endToEnd.status === "PASS" && allTrue(endToEnd.checks));
check("finite-language lower bound", endToEnd.certificate.named_acquirer_outflow_lower_bound === 10);
check("finite-language exact value", endToEnd.certificate.named_acquirer_outflow_exact_value === 10);
check("end-to-end scope", endToEnd.certificate.deployment_wide === false);
const resultNames = {canonical: "canonical_result.v3.json", capability: "capability_certificate.v3.json", coverage: "coverage_certificate.v3.json", outage: "outage_result.v3.json", recovery: "recovery_result.v3.json", source: "source_coverage_kernel.v1.json"};
for (const [key, name] of Object.entries(resultNames)) {
  check(`end-to-end ${key} binding`, lower(endToEnd.input_sha256[key]) === entryHash(execution, `results/${name}`));
}
check("end-to-end manifest identity", lower(endToEnd.input_sha256.manifest) === manifestId);
check("end-to-end manifest digest", lower(endToEnd.input_sha256.manifest_digest) === entryHash(execution, "project/config/code_manifest.v1.sha256"));
check("canonical manifest binding", lower(canonical.source_binding.code_manifest_sha256) === manifestId);
check("canonical source binding", lower(canonical.source_binding.source_coverage_result_sha256) === entryHash(execution, "results/source_coverage_kernel.v1.json"));
for (const [label, result] of [["outage", outage], ["recovery", recovery]]) {
  check(`${label} canonical binding`, lower(result.source_binding.canonical_result_sha256) === entryHash(execution, "results/canonical_result.v3.json"));
  check(`${label} manifest binding`, lower(result.source_binding.code_manifest_sha256) === manifestId);
}

const fidelity = readZipEntries(fidelityZip);
check("code-fidelity entry count", fidelity.size === 16, String(fidelity.size));
const fidelityForbidden = [...fidelity.keys()].filter((name) => forbiddenName.test(name));
check("code-fidelity package has no private entries", fidelityForbidden.length === 0, fidelityForbidden.join(", "));
check("fidelity manifest identity", lower(fidelity.get("config/code_manifest.v1.sha256")?.toString("utf8")) === manifestId);
check("fidelity manifest bytes", entryHash(fidelity, "config/code_manifest.v1.json") === manifestJsonDigest);
const binding = json(fidelity, "results/code_manifest_binding.v1.json");
const mutations = json(fidelity, "results/code_manifest_mutation_matrix.v1.json");
check("code-to-manifest fidelity", binding.status === "PASS" && lower(binding.manifest_sha256) === manifestId);
check("six fidelity mutations caught", mutations.status === "PASS" && mutations.caught === 6 && mutations.total === 6);
check("mutation matrix manifest binding", lower(mutations.baseline_manifest_sha256) === manifestId);
for (const [name, data] of fidelity) {
  if (codeManifest.files[name]) check(`fidelity pinned file ${name}`, sha256(data) === lower(codeManifest.files[name]));
}

if (failures.length) {
  console.error("TWO_HOST_V5_PUBLIC_VERIFICATION=FAIL");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`PUBLIC_EXECUTION_ARCHIVE_SHA256=${EXECUTION_SHA256.toUpperCase()}`);
console.log(`CODE_FIDELITY_ARCHIVE_SHA256=${FIDELITY_SHA256.toUpperCase()}`);
console.log(`CODE_MANIFEST_SHA256=${CODE_MANIFEST_SHA256.toUpperCase()}`);
console.log("FINITE_LANGUAGE_PAYMENT_FLOOR=10");
console.log("FINITE_LANGUAGE_PAYMENT_EXACT=10");
console.log("SOURCE_MUTATIONS_CAUGHT=14/14");
console.log("CODE_MUTATIONS_CAUGHT=6/6");
console.log("TWO_HOST_V5_PUBLIC_VERIFICATION=PASS");
