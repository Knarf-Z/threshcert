import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const cohortPath = path.join(root, "cohort.ethereum-mainnet.v1.json");
const cohort = JSON.parse(await readFile(cohortPath, "utf8"));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const exists = async (file) => {
  try { await readFile(file); return true; } catch { return false; }
};

const rows = [];
const manifestFiles = [
  "README.md",
  "SURVEY_REPORT.md",
  "aggregate_results_v2.mjs",
  "cohort.ethereum-mainnet.v1.json",
  "capture_runtime.mjs",
  "materialize_sourcify_artifact.mjs",
  "screen_contract_v2.mjs",
  "test_screen_contract_v2.mjs",
  "verify_manifest_v2.mjs",
  "policy.direct-closed-contract.v2.json",
];

for (const subject of cohort.subjects) {
  const resultRelative = `results_v2/${subject.id}.json`;
  const result = JSON.parse(await readFile(path.join(root, resultRelative), "utf8"));
  const status = Object.fromEntries(result.checks.map((item) => [`${item.layer}/${item.name}`, item.status]));
  rows.push({
    id: subject.id,
    protocol: subject.protocol,
    role: subject.role,
    address: subject.address,
    officialSource: subject.officialSource,
    commonStaticScreen: result.commonStaticScreen,
    abiInventory: result.abiInventory,
    directCreation: status["identity/directCreation"],
    runtimeTemplate: status["template/runtimeTemplateModuloRelocations"],
    delegatecallPolicy: status["controlFlow/forbid:delegatecall"],
    proxySlots: status["controlFlow/proxySlots"],
    minimalProxy: status["controlFlow/minimalProxyFingerprint"],
    closedContractAdmission: result.closedContractAdmission,
    commonStaticReasons: result.commonStaticReasons,
    blockingReasons: result.blockingReasons,
  });
  manifestFiles.push(`records/${subject.id}.json`, resultRelative);
  for (const relative of [`sourcify/${subject.id}.json`, `artifacts/${subject.id}.json`]) {
    if (await exists(path.join(root, relative))) manifestFiles.push(relative);
  }
}

const count = (field, value) => rows.filter((row) => row[field] === value).length;
const aggregate = {
  schema: "third-party-contract-survey-aggregate/v2",
  cohort: {
    id: cohort.cohortId,
    chainId: cohort.chainId,
    pinnedBlock: cohort.pinnedBlock,
    pinnedBlockHash: cohort.pinnedBlockHash,
    subjectCount: rows.length,
    selectionRule: cohort.selectionRule,
  },
  interpretation: {
    sampling: "Purposive predeclared stress sample; no prevalence estimate is claimed.",
    commonStaticPass: "All reusable provenance, direct-creation identity, runtime-template, and direct-control-flow checks passed. This is only a candidate for contract-specific semantic analysis.",
    failClosed: "The required evidence was not fully discharged. This is not a claim that the contract or protocol is insecure.",
  },
  counts: {
    commonStaticPass: count("commonStaticScreen", "PASS"),
    commonStaticFail: count("commonStaticScreen", "FAIL"),
    commonStaticIncomplete: count("commonStaticScreen", "INCOMPLETE"),
    abiAvailable: count("abiInventory", "AVAILABLE"),
    fullAdmissionPass: count("closedContractAdmission", "PASS"),
    fullAdmissionFailClosed: count("closedContractAdmission", "FAIL_CLOSED"),
    delegatecallPolicyFail: count("delegatecallPolicy", "FAIL"),
    proxySlotFail: count("proxySlots", "FAIL"),
    minimalProxyFail: count("minimalProxy", "FAIL"),
  },
  rows,
};

const csvFields = [
  "id", "protocol", "role", "address", "commonStaticScreen", "abiInventory",
  "directCreation", "runtimeTemplate", "delegatecallPolicy", "proxySlots",
  "minimalProxy", "closedContractAdmission", "commonStaticReasons",
];
const quote = (value) => `"${String(Array.isArray(value) ? value.join("; ") : value ?? "").replaceAll('"', '""')}"`;
const csv = [csvFields.join(","), ...rows.map((row) => csvFields.map((field) => quote(row[field])).join(","))].join("\n") + "\n";

const aggregateRelative = "aggregate.ethereum-mainnet.v2.json";
const csvRelative = "aggregate.ethereum-mainnet.v2.csv";
await writeFile(path.join(root, aggregateRelative), `${JSON.stringify(aggregate, null, 2)}\n`, "utf8");
await writeFile(path.join(root, csvRelative), csv, "utf8");
manifestFiles.push(aggregateRelative, csvRelative);

const manifest = [];
for (const relative of [...new Set(manifestFiles)].sort()) {
  const bytes = await readFile(path.join(root, relative));
  manifest.push(`${sha(bytes)}  ${relative.replaceAll("\\", "/")}`);
}
await writeFile(path.join(root, "MANIFEST.v2.sha256"), `${manifest.join("\n")}\n`, "utf8");
console.log(`SUBJECTS=${rows.length}`);
console.log(`COMMON_STATIC=PASS:${aggregate.counts.commonStaticPass},FAIL:${aggregate.counts.commonStaticFail},INCOMPLETE:${aggregate.counts.commonStaticIncomplete}`);
console.log(`FULL_ADMISSION=PASS:${aggregate.counts.fullAdmissionPass},FAIL_CLOSED:${aggregate.counts.fullAdmissionFailClosed}`);
console.log(`AGGREGATE=${path.join(root, aggregateRelative)}`);
