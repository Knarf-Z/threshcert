// Verifier for the controlled paid-threshold-response positive certificate.
//
// It checks four things that the paper depends on and that no other module can
// establish:
//   1. the extracted subtree is byte-identical to the frozen archive;
//   2. the recorded canonical result matches its pinned digest;
//   3. the run metadata does not participate in that digest, so a different
//      host may differ in PIDs and timings without moving the canonical hash;
//   4. the experiment re-runs from the extracted tree and reproduces the
//      canonical result byte for byte, and its own verifier passes.
//
// Every number the paper quotes is asserted individually below, so a drift
// between the manuscript and the record fails here rather than in review.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const root = path.dirname(fileURLToPath(import.meta.url));
const frozenZip = path.join(root, "frozen", "ptr_host1_v2.zip");
const extracted = path.join(root, "extracted");

const FROZEN_ZIP_SHA256 =
  "f64ef30657cc64940155f2ec37808e72154dec76255172d6e11412e65b603415";
const CANONICAL_SHA256 =
  "492ada8c05d24193fec4821d9038c851eab8861214145974a12b36b269bf8148";
const NON_DETERMINISTIC = new Set(["results/run_metadata.v2.json"]);

const failures = [];
function check(name, condition, detail = "") {
  if (!condition) failures.push(detail ? `${name}: ${detail}` : name);
  return condition;
}

function sha256File(file) {
  return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

// --- minimal zip reader: central directory walk, stored + deflate entries ---
function readZipEntries(file) {
  const buf = fs.readFileSync(file);
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("zip end-of-central-directory not found");
  const count = buf.readUInt16LE(eocd + 10);
  let offset = buf.readUInt32LE(eocd + 16);
  const entries = new Map();
  for (let i = 0; i < count; i++) {
    if (buf.readUInt32LE(offset) !== 0x02014b50) throw new Error("bad central header");
    const method = buf.readUInt16LE(offset + 10);
    const compressedSize = buf.readUInt32LE(offset + 20);
    const nameLength = buf.readUInt16LE(offset + 28);
    const extraLength = buf.readUInt16LE(offset + 30);
    const commentLength = buf.readUInt16LE(offset + 32);
    const localOffset = buf.readUInt32LE(offset + 42);
    const name = buf.toString("utf8", offset + 46, offset + 46 + nameLength);
    offset += 46 + nameLength + extraLength + commentLength;
    if (name.endsWith("/")) continue;
    const localNameLength = buf.readUInt16LE(localOffset + 26);
    const localExtraLength = buf.readUInt16LE(localOffset + 28);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    const raw = buf.subarray(dataStart, dataStart + compressedSize);
    const data = method === 0 ? raw : zlib.inflateRawSync(raw);
    entries.set(name.replace(/\\/g, "/"), data);
  }
  return entries;
}

function walk(dir, base = dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__pycache__" || entry.name === ".venv") continue;
      out.push(...walk(full, base));
    } else {
      out.push(path.relative(base, full).split(path.sep).join("/"));
    }
  }
  return out;
}

function python(args, cwd) {
  for (const [cmd, prefix] of [
    ["py", ["-3"]],
    ["python3", []],
    ["python", []],
  ]) {
    const probe = spawnSync(cmd, [...prefix, "--version"], { stdio: "ignore", shell: false });
    if (!probe.error && probe.status === 0) {
      return spawnSync(cmd, [...prefix, ...args], {
        cwd,
        encoding: "utf8",
        shell: false,
        env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
      });
    }
  }
  throw new Error("Python 3 not found");
}

// 1. the frozen archive is the pinned one
check(
  "frozen archive digest",
  sha256File(frozenZip) === FROZEN_ZIP_SHA256,
  `expected ${FROZEN_ZIP_SHA256}`
);

// 2. the extracted subtree equals the frozen archive
const zipEntries = readZipEntries(frozenZip);
const onDisk = walk(extracted).sort();
check(
  "extracted file count",
  onDisk.length === zipEntries.size,
  `${onDisk.length} on disk vs ${zipEntries.size} in the archive`
);
let identical = true;
for (const relative of onDisk) {
  const archived = zipEntries.get(relative);
  if (!archived) {
    identical = false;
    failures.push(`extracted/${relative} is absent from the frozen archive`);
    continue;
  }
  const actual = fs.readFileSync(path.join(extracted, relative));
  if (!actual.equals(archived)) {
    identical = false;
    failures.push(`extracted/${relative} differs from the frozen archive`);
  }
}
check("extracted subtree matches frozen archive", identical);

// 3. the canonical result carries the pinned digest, and metadata is excluded
const canonicalPath = path.join(extracted, "results", "canonical_result.v2.json");
check(
  "canonical result digest",
  sha256File(canonicalPath) === CANONICAL_SHA256,
  `expected ${CANONICAL_SHA256}`
);
const manifest = fs.readFileSync(path.join(extracted, "MANIFEST.sha256"), "utf8");
for (const excluded of NON_DETERMINISTIC) {
  check(
    `run metadata excluded from the manifest (${excluded})`,
    !manifest.includes(excluded),
    "non-deterministic content must not participate in the canonical digest"
  );
}
check(
  "canonical result is inside the manifest",
  manifest.includes("results/canonical_result.v2.json")
);

// 4. re-run from the extracted tree and compare byte for byte
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "ptr-v2-"));
const replayCanonical = path.join(scratch, "canonical.json");
const replayMetadata = path.join(scratch, "metadata.json");
const unit = python(["-m", "unittest", "discover", "-s", "tests"], extracted);
const unitOutput = `${unit.stdout ?? ""}${unit.stderr ?? ""}`;
const unitCount = /Ran (\d+) tests/.exec(unitOutput);
check("unit tests", unit.status === 0, unitOutput.trim().split("\n").slice(-3).join(" | "));

const run = python(
  ["scripts/run_host1.py", "--canonical", replayCanonical, "--metadata", replayMetadata],
  extracted
);
const runOutput = `${run.stdout ?? ""}${run.stderr ?? ""}`;
check("experiment run", run.status === 0, runOutput.trim().split("\n").slice(-3).join(" | "));
const field = (name) => {
  const match = new RegExp(`^${name}=(.*)$`, "m").exec(runOutput);
  return match ? match[1].trim() : null;
};

check(
  "replayed canonical result is byte-identical",
  fs.existsSync(replayCanonical) && sha256File(replayCanonical) === CANONICAL_SHA256
);
check(
  "run metadata does not move the canonical digest",
  fs.existsSync(replayMetadata) &&
    sha256File(replayMetadata) !== sha256File(canonicalPath)
);

const verify = python(["scripts/verify_results.py"], extracted);
const verifyOutput = `${verify.stdout ?? ""}${verify.stderr ?? ""}`;
check("independent result verification", /RESULT_VERIFICATION=PASS/.test(verifyOutput));

const manifestCheck = python(["scripts/verify_manifest.py"], extracted);
check(
  "nested manifest verification",
  /MANIFEST_VERIFICATION=PASS/.test(`${manifestCheck.stdout ?? ""}${manifestCheck.stderr ?? ""}`)
);

// --- the individual numbers the manuscript quotes ---
const canonical = JSON.parse(fs.readFileSync(canonicalPath, "utf8"));
const q = canonical.quantities;
const catalog = canonical.route_catalog;
const claims = [
  ["schema is v2", canonical.schema === "paid-threshold-response-host1/v2"],
  ["840 ordered routes", catalog.routes_enumerated === 840],
  ["every route floor is ledger-derived", catalog.all_floors_ledger_derived === true],
  ["theory cover is 10", q.theory_cover === 10],
  ["catalog certificate is 10", q.catalog_certificate === 10],
  ["observed minimum is 10", q.observed_minimum === 10],
  ["baseline execution floor is 10", q.baseline_execution_floor === 10],
  ["24 minimizing routes", catalog.minimizing_routes === 24],
  ["coalition {4,5,6,7} floors at 22", catalog.coalition_floors["4,5,6,7"] === 22],
  ["baseline is certified", canonical.baseline.report.status === "CERTIFIED"],
  [
    "four counted responders come from distinct processes",
    canonical.multiprocess_smoke.distinct_worker_count === 4,
  ],
  ["seven operator processes are spawned", canonical.scope.operator_processes_spawned === 7],
  ["deployment-wide is not claimed", canonical.scope.deployment_wide === false],
  [
    "hardware non-exportability is not claimed",
    canonical.scope.hardware_non_exportability_proved === false,
  ],
  ["a trusted dealer is disclosed", canonical.scope.trusted_dealer === true],
  ["one physical host is disclosed", canonical.scope.physical_hosts === 1],
  ["every embedded check passes", Object.values(canonical.checks).every(Boolean)],
];
for (const [name, ok] of claims) check(name, ok);

// ablation matrix: one FAIL_COUNTEREXAMPLE per ablation, on its target gate
let matrixOk = true;
let offDiagonalFailures = 0;
for (const [name, entry] of Object.entries(canonical.ablations)) {
  for (const [gate, verdict] of Object.entries(entry.report.gates)) {
    if (gate === entry.target_gate) {
      if (verdict.status !== "FAIL_COUNTEREXAMPLE") matrixOk = false;
    } else if (!["PASS", "NOT_APPLICABLE"].includes(verdict.status)) {
      matrixOk = false;
      offDiagonalFailures += 1;
    }
  }
  if (entry.report.status !== "REFUTED") matrixOk = false;
  void name;
}
check("ablation matrix is diagonal", matrixOk && offDiagonalFailures === 0);

const cases = canonical.verdict_cases;
check(
  "unknown and refuted are not conflated",
  cases.missing_coverage_evidence.report.status === "UNKNOWN" &&
    cases.missing_coverage_evidence.report.gates.B5.status === "FAIL_CLOSED_MISSING_EVIDENCE" &&
    cases.missing_ordering_evidence.report.status === "UNKNOWN" &&
    cases.missing_ordering_evidence.report.gates.B3.status === "FAIL_CLOSED_MISSING_EVIDENCE" &&
    cases.explicit_bypass_trace.report.status === "REFUTED" &&
    cases.explicit_bypass_trace.report.gates.B5.status === "FAIL_COUNTEREXAMPLE"
);

console.log(`PTR_HOST1_V2_UNIT_TESTS=${unit.status === 0 ? "PASS" : "FAIL"} tests=${unitCount ? unitCount[1] : "?"}`);
console.log(`PTR_HOST1_V2_ROUTES=${field("ROUTES_ENUMERATED") ?? catalog.routes_enumerated}`);
console.log(`PTR_HOST1_V2_THEORY_COVER=${q.theory_cover}`);
console.log(`PTR_HOST1_V2_CATALOG_CERTIFICATE=${q.catalog_certificate}`);
console.log(`PTR_HOST1_V2_OBSERVED_MINIMUM=${q.observed_minimum}`);
console.log(`PTR_HOST1_V2_EXPENSIVE_COALITION_FLOOR=${catalog.coalition_floors["4,5,6,7"]}`);
console.log(`PTR_HOST1_V2_ABLATION_MATRIX=${matrixOk && offDiagonalFailures === 0 ? "PASS" : "FAIL"}`);
console.log(
  `PTR_HOST1_V2_TRI_STATE=${
    cases.missing_coverage_evidence.report.status === "UNKNOWN" &&
    cases.explicit_bypass_trace.report.status === "REFUTED"
      ? "PASS"
      : "FAIL"
  }`
);
console.log(`PTR_HOST1_V2_FROZEN_ZIP_SHA256=${FROZEN_ZIP_SHA256}`);
console.log(`PTR_HOST1_V2_CANONICAL_SHA256=${CANONICAL_SHA256}`);

if (failures.length) {
  for (const failure of failures) console.error(`PTR_HOST1_V2_FAILURE=${failure}`);
  console.log("PTR_HOST1_V2=FAIL");
  process.exit(1);
}
console.log("PTR_HOST1_V2=PASS");
