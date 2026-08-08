import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const root = path.dirname(fileURLToPath(import.meta.url));
const executionZip = path.join(root, "frozen", "two_host_execution_evidence.public.zip");
const fidelityZip = path.join(root, "frozen", "code_fidelity_evidence.zip");

const EXECUTION_SHA256 =
  "e91b8209867db8e366b7dc8a37cee64310fa998643fa3eb86d295209e59d5d37";
const FIDELITY_SHA256 =
  "fdb62bcedf1a63aa672c34239f698844ac2be092a32e3e46d64118ed5a9aca9b";
const SOURCE_ARCHIVE_SHA256 =
  "2703aee4335402037181a18e4f5afeefc3d99f5da2aeab35d0de9eb331dee98e";
const CODE_MANIFEST_SHA256 =
  "7d533f5ce311a01734608d4eaa2a8f44d77241c4425a5d0cf9c30949d0694871";

const failures = [];
function check(name, condition, detail = "") {
  if (!condition) failures.push(detail ? `${name}: ${detail}` : name);
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
const forbiddenName =
  /(^|\/)(private_metadata|secrets?|__pycache__)(\/|$)|\.pyc$|\.nonces?\.log$|\.before-/i;
const forbiddenEntries = [...execution.keys()].filter((name) => forbiddenName.test(name));
check("public package has no private entries", forbiddenEntries.length === 0, forbiddenEntries.join(", "));
check("public package excludes nested provenance ZIP", !execution.has("provenance/host2_evidence_original.zip"));

const manifestText = execution.get("MANIFEST.sha256")?.toString("utf8") ?? "";
const manifest = new Map(
  manifestText.trimEnd().split("\n").filter(Boolean).map((line) => {
    const match = line.match(/^([0-9a-f]{64})  (.+)$/);
    return match ? [match[2], match[1]] : [`<malformed:${line}>`, "MALFORMED"];
  }),
);
check("public manifest covers every payload", manifest.size === execution.size - 1);
for (const [name, digest] of manifest) {
  check(`manifest entry ${name}`, execution.has(name) && sha256(execution.get(name)) === digest);
}

const release = json(execution, "PUBLIC_RELEASE.json");
check("public-release schema", release.schema === "ptr-two-host-public-execution-evidence/v1");
check("source archive binding", release.source_archive_sha256.toLowerCase() === SOURCE_ARCHIVE_SHA256);
check("private metadata excluded", release.privacy_transform.excluded_private_metadata === true);
check("private provenance excluded", release.privacy_transform.excluded_provenance_subtree === true);

const canonical = json(execution, "results/canonical_result.v3.json");
const q = canonical.quantities;
const catalog = canonical.route_catalog;
check("canonical schema", canonical.schema === "paid-threshold-response-two-host/v3");
check("run passed", canonical.run_passed === true && canonical.failed_checks.length === 0);
check("theory cover is 10", q.theory_cover === 10);
check("baseline execution floor is 10", q.baseline_execution_floor === 10);
check("catalog certificate is 10", q.catalog_certificate === 10);
check("observed minimum is 10", q.observed_minimum === 10);
check("remote-only coalition floors at 19", q.remote_only_execution_floor === 19);
check("expensive coalition floors at 22", q.expensive_execution_floor === 22);
check("840 routes enumerated", catalog.routes_enumerated === 840 && catalog.eligible_routes === 840);
check("route catalog is complete", catalog.catalog_complete === true && catalog.incomplete_routes === 0);
check("all route floors are ledger-derived", catalog.all_floors_ledger_derived === true);
check("24 minimizing routes", catalog.minimizing_routes === 24);
check("two-host run class", canonical.scope.run_class === "CERTIFIED_TWO_HOST");
check("two-host separation", canonical.scope.host_separation_status === "PASS");
check("key isolation", canonical.scope.key_isolation_status === "PASS");
check("finite-language scope", canonical.scope.deployment_wide === false);

const outage = json(execution, "results/outage_result.v3.json");
check("outage checks", Object.values(outage.checks).every(Boolean));
const recovery = json(execution, "results/recovery_result.v3.json");
check("recovery checks", Object.values(recovery.checks).every(Boolean));

const capability = json(execution, "results/capability_certificate.v3.json");
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
check("sealed composition baseline", coverage.baseline.status === "SEALED");
check("coverage mutations caught", coverage.checks.every_mutation_caught === true);

const transcript = execution.get("results/verify_two_host.transcript.txt")?.toString("utf8") ?? "";
check("independent two-host verifier transcript", /TWO_HOST_VERIFICATION=PASS/.test(transcript));

const fidelity = readZipEntries(fidelityZip);
const binding = json(fidelity, "results/code_manifest_binding.v1.json");
const mutations = json(fidelity, "results/code_manifest_mutation_matrix.v1.json");
check("code-to-manifest fidelity", binding.status === "PASS");
check("code manifest binding", binding.manifest_sha256.toLowerCase() === CODE_MANIFEST_SHA256);
check(
  "six fidelity mutations caught",
  mutations.status === "PASS" && mutations.caught === 6 && mutations.total === 6,
);
check(
  "mutation matrix manifest binding",
  mutations.baseline_manifest_sha256.toLowerCase() === CODE_MANIFEST_SHA256,
);

if (failures.length) {
  console.error("TWO_HOST_V4_PUBLIC_VERIFICATION=FAIL");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`PUBLIC_EXECUTION_ARCHIVE_SHA256=${EXECUTION_SHA256.toUpperCase()}`);
console.log(`CODE_FIDELITY_ARCHIVE_SHA256=${FIDELITY_SHA256.toUpperCase()}`);
console.log("TWO_HOST_VERIFICATION=PASS");
console.log("CODE_TO_MANIFEST_FIDELITY=PASS");
console.log("MUTATIONS_CAUGHT=6/6");
console.log("TWO_HOST_V4_PUBLIC_VERIFICATION=PASS");
