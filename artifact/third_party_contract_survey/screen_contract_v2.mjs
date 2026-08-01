import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1]);
const recordPath = args.get("--record");
const artifactPath = args.get("--artifact");
const policyPath = args.get("--policy");
const outputPath = args.get("--out");
if (!recordPath || !policyPath || !outputPath) {
  throw new Error("usage: node screen_contract.mjs --record RECORD.json --policy POLICY.json --out RESULT.json [--artifact ARTIFACT.json]");
}

const sha = (value) => createHash("sha256").update(value).digest("hex");
const hexBytes = (value) => {
  if (typeof value !== "string" || !/^0x(?:[0-9a-fA-F]{2})*$/.test(value)) throw new Error("malformed hex byte string");
  return Buffer.from(value.slice(2), "hex");
};
const normalizedHex = (value) => `0x${hexBytes(value).toString("hex")}`;

function bytecodeField(value) {
  if (typeof value === "string") return value;
  if (value && typeof value.object === "string") return value.object.startsWith("0x") ? value.object : `0x${value.object}`;
  return undefined;
}

function flattenReferences(referenceObject) {
  const references = [];
  for (const value of Object.values(referenceObject ?? {})) {
    if (Array.isArray(value)) references.push(...value);
    else for (const nested of Object.values(value ?? {})) references.push(...nested);
  }
  return references.map(({ start, length }) => ({ start: Number(start), length: Number(length) }));
}

function executableSlice(runtime) {
  if (runtime.length < 3) return runtime;
  const metadataLength = runtime.readUInt16BE(runtime.length - 2);
  const start = runtime.length - metadataLength - 2;
  if (start < 0 || start >= runtime.length - 2) return runtime;
  const cborHead = runtime[start];
  if (cborHead < 0xa0 || cborHead > 0xbf) return runtime;
  return runtime.subarray(0, start);
}

function opcodeCounts(runtimeHex) {
  const raw = hexBytes(runtimeHex);
  const code = executableSlice(raw);
  const counts = new Map();
  for (let pc = 0; pc < code.length; pc += 1) {
    const opcode = code[pc];
    counts.set(opcode, (counts.get(opcode) ?? 0) + 1);
    if (opcode >= 0x60 && opcode <= 0x7f) pc += opcode - 0x5f;
  }
  return {
    runtimeBytes: raw.length,
    executableBytes: code.length,
    call: counts.get(0xf1) ?? 0,
    callcode: counts.get(0xf2) ?? 0,
    delegatecall: counts.get(0xf4) ?? 0,
    staticcall: counts.get(0xfa) ?? 0,
    create: counts.get(0xf0) ?? 0,
    create2: counts.get(0xf5) ?? 0,
    selfdestruct: counts.get(0xff) ?? 0,
  };
}

function runtimeTemplateCheck(actualHex, artifact) {
  const templateHex = bytecodeField(artifact?.deployedBytecode ?? artifact?.evm?.deployedBytecode?.object);
  if (!templateHex) return { status: "NOT_EVALUATED", detail: "artifact has no deployed bytecode" };
  const actual = hexBytes(actualHex);
  const template = hexBytes(templateHex);
  if (actual.length !== template.length) {
    return { status: "FAIL", detail: `runtime length ${actual.length} != template length ${template.length}` };
  }
  const immutableReferences = flattenReferences(
    artifact?.immutableReferences ?? artifact?.evm?.deployedBytecode?.immutableReferences,
  );
  const linkReferences = flattenReferences(
    artifact?.deployedLinkReferences ?? artifact?.evm?.deployedBytecode?.linkReferences,
  );
  const ignored = new Set();
  for (const reference of [...immutableReferences, ...linkReferences]) {
    if (!Number.isInteger(reference.start) || !Number.isInteger(reference.length) || reference.start < 0 || reference.length < 0 || reference.start + reference.length > actual.length) {
      return { status: "FAIL", detail: "artifact contains an invalid relocation range" };
    }
    for (let i = reference.start; i < reference.start + reference.length; i += 1) ignored.add(i);
  }
  for (let i = 0; i < actual.length; i += 1) {
    if (!ignored.has(i) && actual[i] !== template[i]) {
      return { status: "FAIL", detail: `runtime differs from template at byte ${i}` };
    }
  }
  return {
    status: "PASS",
    detail: `exact template match outside ${immutableReferences.length} immutable and ${linkReferences.length} link-reference ranges`,
  };
}

function mutatingAbi(artifact) {
  const abi = artifact?.abi;
  if (!Array.isArray(abi)) return { status: "NOT_EVALUATED", entries: [], fallbackOrReceive: undefined };
  const entries = abi
    .filter((item) => item.type === "function" && !["view", "pure"].includes(item.stateMutability))
    .map((item) => `${item.name}(${(item.inputs ?? []).map((input) => input.type).join(",")})`)
    .sort();
  return {
    status: "PASS",
    entries,
    fallbackOrReceive: abi.some((item) => ["fallback", "receive"].includes(item.type)),
  };
}

const recordBytes = await readFile(path.resolve(recordPath));
const record = JSON.parse(recordBytes);
const policyBytes = await readFile(path.resolve(policyPath));
const policy = JSON.parse(policyBytes);
const artifactBytes = artifactPath ? await readFile(path.resolve(artifactPath)) : undefined;
const artifact = artifactBytes ? JSON.parse(artifactBytes) : undefined;
const runtimeHex = normalizedHex(record.runtime?.code);
const runtimeHash = sha(hexBytes(runtimeHex));
const checks = [];
const add = (layer, name, status, detail) => checks.push({ layer, name, status, detail });

add("provenance", "recordSchema", record.schema === "third-party-runtime-record/v1" || record.schema === "overlapping-pool-deployment-admission/v1" ? "PASS" : "FAIL", record.schema ?? "missing");
add("provenance", "chainPin", Number(record.chain?.chainId) > 0 && /^0x[0-9a-fA-F]{64}$/.test(record.chain?.blockHash ?? "") ? "PASS" : "FAIL", `${record.chain?.chainId ?? "?"}:${record.chain?.blockNumber ?? "?"}:${record.chain?.blockHash ?? "?"}`);
add("provenance", "runtimeHash", record.runtime?.sha256?.toLowerCase() === runtimeHash ? "PASS" : "FAIL", runtimeHash);

if (record.deployment) {
  const direct = record.deployment.to === null;
  const success = record.deployment.receiptStatus === "success";
  add("identity", "directCreation", direct ? "PASS" : "FAIL", direct ? "top-level creation" : "deployment transaction has a destination");
  add("identity", "successfulReceipt", success ? "PASS" : "FAIL", record.deployment.receiptStatus ?? "missing");
  if (artifact) {
    const creation = bytecodeField(artifact.bytecode ?? artifact?.evm?.bytecode?.object);
    const prefix = creation && normalizedHex(record.deployment.input).startsWith(normalizedHex(creation));
    add("identity", "creationBytecodePrefix", prefix ? "PASS" : "FAIL", prefix ? "deployment input begins with verified creation bytecode" : "creation bytecode prefix mismatch or unavailable");
  } else add("identity", "creationBytecodePrefix", "NOT_EVALUATED", "no artifact supplied");
} else {
  add("identity", "directCreation", "NOT_EVALUATED", "deployment transaction not supplied");
  add("identity", "successfulReceipt", "NOT_EVALUATED", "deployment receipt not supplied");
  add("identity", "creationBytecodePrefix", "NOT_EVALUATED", "deployment input or artifact not supplied");
}

if (artifact) {
  add("template", "artifactHash", !record.compiler?.artifactSha256 || record.compiler.artifactSha256.toLowerCase() === sha(artifactBytes) ? "PASS" : "FAIL", sha(artifactBytes));
  const template = runtimeTemplateCheck(runtimeHex, artifact);
  add("template", "runtimeTemplateModuloRelocations", template.status, template.detail);
} else {
  add("template", "artifactHash", "NOT_EVALUATED", "no artifact supplied");
  add("template", "runtimeTemplateModuloRelocations", "NOT_EVALUATED", "no artifact supplied");
}

const opcodes = opcodeCounts(runtimeHex);
for (const opcode of policy.forbiddenOpcodes ?? []) {
  const count = opcodes[opcode];
  add("controlFlow", `forbid:${opcode}`, count === 0 ? "PASS" : "FAIL", `${count ?? "unknown"} executable occurrences`);
}
const slots = record.proxySlots;
if (policy.requireZeroProxySlots) {
  if (!slots) add("controlFlow", "proxySlots", "NOT_EVALUATED", "EIP-1967 slots not supplied");
  else {
    const nonzero = Object.entries(slots).filter(([, value]) => BigInt(value) !== 0n);
    add("controlFlow", "proxySlots", nonzero.length === 0 ? "PASS" : "FAIL", nonzero.length === 0 ? "implementation/admin/beacon slots are zero" : `nonzero slots: ${nonzero.map(([name]) => name).join(",")}`);
  }
}
const minimalProxy = /^0x363d3d373d3d3d363d73[0-9a-f]{40}5af43d82803e903d91602b57fd5bf3$/i.test(runtimeHex);
add("controlFlow", "minimalProxyFingerprint", minimalProxy ? "FAIL" : "PASS", minimalProxy ? "EIP-1167 runtime" : "not the standard EIP-1167 runtime");

const abi = mutatingAbi(artifact);
add("abi", "abiAvailable", abi.status, abi.status === "PASS" ? `${abi.entries.length} mutating entries` : "no artifact ABI supplied");
if (abi.status === "PASS") {
  if (policy.forbidFallbackOrReceive) add("abi", "fallbackOrReceive", abi.fallbackOrReceive ? "FAIL" : "PASS", String(abi.fallbackOrReceive));
  if (Array.isArray(policy.allowedMutatingSignatures)) {
    const equal = JSON.stringify(abi.entries) === JSON.stringify([...policy.allowedMutatingSignatures].sort());
    add("abi", "mutatingEntryClosure", equal ? "PASS" : "FAIL", JSON.stringify(abi.entries));
  } else add("abi", "mutatingEntryClosure", "NOT_EVALUATED", JSON.stringify(abi.entries));
}

for (const name of policy.requiredSemanticChecks ?? []) {
  const evidence = record.semanticCertificate?.[name];
  const digestValid = /^[0-9a-f]{64}$/i.test(evidence?.evidenceSha256 ?? "");
  add("semanticIncidence", name, evidence?.status === "PASS" && digestValid ? "PASS" : "NOT_EVALUATED", evidence?.detail ?? "no contract-specific machine-checkable evidence supplied");
}

const requiredLayers = new Set(policy.requiredLayers ?? ["provenance", "identity", "template", "controlFlow", "semanticIncidence"]);
const requiredChecks = checks.filter((item) => requiredLayers.has(item.layer));
const failures = requiredChecks.filter((item) => item.status !== "PASS");
const commonLayers = new Set(["provenance", "identity", "template", "controlFlow"]);
const commonChecks = checks.filter((item) => commonLayers.has(item.layer));
const commonFailures = commonChecks.filter((item) => item.status === "FAIL");
const commonUnknowns = commonChecks.filter((item) => item.status === "NOT_EVALUATED");
const commonStaticScreen = commonFailures.length > 0
  ? "FAIL"
  : commonUnknowns.length > 0
    ? "INCOMPLETE"
    : "PASS";
const result = {
  schema: "third-party-closed-contract-screen/v2",
  subject: record.subject ?? { address: record.deployment?.contractAddress },
  policy: { id: policy.id, sha256: sha(policyBytes) },
  inputs: {
    record: path.resolve(recordPath),
    recordSha256: sha(recordBytes),
    artifact: artifactPath ? path.resolve(artifactPath) : null,
    artifactSha256: artifactBytes ? sha(artifactBytes) : null,
  },
  runtime: { sha256: runtimeHash, opcodes },
  abi: { mutatingEntries: abi.entries, fallbackOrReceive: abi.fallbackOrReceive },
  checks,
  commonStaticScreen,
  commonStaticReasons: [...commonFailures, ...commonUnknowns].map((item) => `${item.layer}/${item.name}:${item.status}`),
  abiInventory: abi.status === "PASS" ? "AVAILABLE" : "NOT_EVALUATED",
  closedContractAdmission: failures.length === 0 ? "PASS" : "FAIL_CLOSED",
  blockingReasons: failures.map((item) => `${item.layer}/${item.name}:${item.status}`),
  interpretation: failures.length === 0
    ? "All policy-required common and contract-specific incidence obligations passed."
    : "This is a fail-closed screening result. It does not establish insecurity; missing semantic evidence and a violated bytecode condition are reported separately.",
};
await mkdir(path.dirname(path.resolve(outputPath)), { recursive: true });
await writeFile(path.resolve(outputPath), `${JSON.stringify(result, null, 2)}\n`, "utf8");
console.log(`CLOSED_CONTRACT_ADMISSION=${result.closedContractAdmission}`);
console.log(`BLOCKING_REASONS=${result.blockingReasons.length}`);
console.log(`RESULT=${path.resolve(outputPath)}`);
