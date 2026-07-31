import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const argumentsMap = new Map();
for (let i = 2; i < process.argv.length; i += 2) argumentsMap.set(process.argv[i], process.argv[i + 1]);
const ARTIFACT = path.resolve(argumentsMap.get("--artifact") ?? path.join(ROOT, "artifacts", "contracts", "OverlappingPoolEscrow.sol", "OverlappingPoolEscrow.json"));
const RECORD = path.resolve(argumentsMap.get("--record") ?? path.join(ROOT, "results", "deployment_admission_local.json"));
const CERTIFICATE = path.resolve(argumentsMap.get("--certificate") ?? path.join(ROOT, "results", "deployment_admission_certificate.json"));
const check = (x, m) => { if (!x) throw new Error(m); };
const sha = (x) => createHash("sha256").update(x).digest("hex");
const bytes = (hex) => Buffer.from(hex.replace(/^0x/, ""), "hex");
const addressWord = (address) => Buffer.from(address.toLowerCase().replace(/^0x/, "").padStart(64, "0"), "hex");
const canonicalAddress = (x) => /^0x[0-9a-fA-F]{40}$/.test(x) && x.toLowerCase();
const signature = (x) => `${x.name}(${(x.inputs ?? []).map((v) => v.type).join(",")})`;

function opcodeCounts(runtime) {
  const raw = bytes(runtime);
  const metadata = raw.readUInt16BE(raw.length - 2) + 2;
  check(metadata <= raw.length, "invalid metadata trailer");
  const code = raw.subarray(0, raw.length - metadata);
  const counts = new Map();
  for (let pc = 0; pc < code.length; pc += 1) {
    const op = code[pc];
    counts.set(op, (counts.get(op) ?? 0) + 1);
    if (op >= 0x60 && op <= 0x7f) pc += op - 0x5f;
  }
  return {
    executableBytes: code.length,
    call: counts.get(0xf1) ?? 0,
    callcode: counts.get(0xf2) ?? 0,
    delegatecall: counts.get(0xf4) ?? 0,
    create: counts.get(0xf0) ?? 0,
    create2: counts.get(0xf5) ?? 0,
    selfdestruct: counts.get(0xff) ?? 0,
  };
}

const artifactText = await readFile(ARTIFACT);
const artifact = JSON.parse(artifactText);
const recordText = await readFile(RECORD);
const record = JSON.parse(recordText);
check(record.schema === "overlapping-pool-deployment-admission/v1", "bad admission schema");
check(record.compiler.version === "0.8.28" && record.compiler.evmRevision === "cancun", "compiler scope mismatch");
check(record.compiler.artifactSha256 === sha(artifactText), "artifact hash mismatch");
check(Number(record.chain.chainId) > 0 && BigInt(record.chain.blockNumber) >= 0n, "bad chain identity");
check(/^0x[0-9a-fA-F]{64}$/.test(record.chain.blockHash), "bad block hash");
check(record.deployment.to === null, "not a direct top-level creation transaction");
check(record.deployment.receiptStatus === "success", "deployment reverted");
check(record.deployment.receiptBlockHash.toLowerCase() === record.chain.blockHash.toLowerCase(), "receipt block hash mismatch");
check(record.deployment.receiptBlockNumber === record.chain.blockNumber, "receipt block number mismatch");
check(record.chain.transactionHashes.at(-1)?.toLowerCase() === record.deployment.transactionHash.toLowerCase(), "deployment must be the block's final transaction for block-end observations");
check(record.chain.transactionHashes[record.deployment.transactionIndex]?.toLowerCase() === record.deployment.transactionHash.toLowerCase(), "transaction index mismatch");
const controller = canonicalAddress(record.constructor.controller);
check(controller, "bad controller address");
const members = record.constructor.members.map(canonicalAddress);
check(members.length === 7 && members.every(Boolean), "bad member addresses");
check(new Set(members).size === 7 && !members.includes("0x0000000000000000000000000000000000000000"), "members not distinct nonzero");
check(!members.includes(controller), "controller/member role conflict");
const constructorWords = [controller, ...members].map((x) => addressWord(x));
const expectedInput = Buffer.concat([bytes(artifact.bytecode), ...constructorWords]);
check(bytes(record.deployment.input).equals(expectedInput), "creation bytecode or constructor arguments mismatch");
const template = bytes(artifact.deployedBytecode);
const actual = bytes(record.runtime.code);
check(actual.length === template.length, "runtime length mismatch");
const refs = Object.values(artifact.immutableReferences ?? {}).flat();
check(refs.length === 3, "unexpected immutable reference count");
const covered = new Set();
for (const ref of refs) {
  check(ref.length === 32 && ref.start >= 0 && ref.start + ref.length <= actual.length, "bad immutable reference");
  check(actual.subarray(ref.start, ref.start + ref.length).equals(addressWord(controller)), "controller immutable mismatch");
  for (let i = ref.start; i < ref.start + ref.length; i += 1) covered.add(i);
}
for (let i = 0; i < actual.length; i += 1) if (!covered.has(i)) check(actual[i] === template[i], `runtime template mismatch at byte ${i}`);
check(record.runtime.sha256 === sha(actual), "runtime hash mismatch");
check(JSON.stringify(record.runtime.immutableReferences) === JSON.stringify(artifact.immutableReferences), "immutable-reference mismatch");
const observed = record.observationsAtDeploymentBlock;
check(canonicalAddress(observed.poolController) === controller, "controller getter mismatch");
check(JSON.stringify(observed.members.map(canonicalAddress)) === JSON.stringify(members), "member getter mismatch");
check(observed.memberCode.length === 7 && observed.memberCode.every((x) => /^0x(?:[0-9a-fA-F]{2})*$/.test(x)), "malformed member code observations");
check(observed.configured === false && observed.completed === false, "deployment state is not fresh");
check(observed.terminalMask === 0 && BigInt(observed.totalAcquisitionCallValue) === 0n, "nonzero terminal projection at deployment");
check(observed.deliveredShareMask === 0, "nonzero delivered-share mask at deployment");
check(observed.acquirer.toLowerCase() === "0x0000000000000000000000000000000000000000", "nonzero acquirer at deployment");
check(observed.credits.length === 7 && observed.credits.every((x) => BigInt(x) === 0n), "nonzero initial credits");
check(JSON.stringify(observed.shareOwners.map(canonicalAddress)) === JSON.stringify(members), "initial share-right owners do not match members");
check(BigInt(observed.balance) === 0n, "nonzero initial balance");
const mutating = artifact.abi.filter((x) => x.type === "function" && !["view", "pure"].includes(x.stateMutability)).map(signature).sort();
check(JSON.stringify(mutating) === JSON.stringify(["acquireFour(uint8[4])", "configureCredits(uint256[7])", "withdraw()"]), "mutating ABI closure mismatch");
check(!artifact.abi.some((x) => ["fallback", "receive"].includes(x.type)), "fallback or receive present");
const ops = opcodeCounts(record.runtime.code);
for (const k of ["callcode", "delegatecall", "create", "create2", "selfdestruct"]) check(ops[k] === 0, `runtime contains ${k}`);
check(ops.call === 1, "runtime must contain the sole guarded withdrawal CALL");
const certificate = {
  schema: "overlapping-pool-deployment-admission-certificate/v1",
  status: "PASS",
  record: "results/deployment_admission_local.json",
  recordSha256: sha(recordText),
  artifact: "artifacts/contracts/OverlappingPoolEscrow.sol/OverlappingPoolEscrow.json",
  artifactSha256: sha(artifactText),
  chain: record.chain,
  contractAddress: record.deployment.contractAddress,
  runtimeSha256: record.runtime.sha256,
  obligations: {
    directCreationIdentity: "PASS",
    constructorClosure: "PASS",
    runtimeTemplateModuloImmutables: "PASS",
    roleSeparatedControllerMembersAndInitialShareOwners: "PASS",
    freshInitialProjection: "PASS",
    mutatingAbiClosure: "PASS",
    nonProxyOpcodeClosure: "PASS",
    memberCodeRestriction: "NONE: member code is observed but not restricted; arbitrary-callee projection neutrality is a separate EVM call/storage-isolation lemma, while Halmos checks the complete mutating-reentry basis on concrete hostile receivers",
  },
  scope: "reproducible local direct deployment; the same record schema can be populated from archive RPC for a public deployment",
};
await mkdir(path.dirname(CERTIFICATE), { recursive: true });
await writeFile(CERTIFICATE, `${JSON.stringify(certificate, null, 2)}\n`);
for (const name of ["DIRECT_CREATION", "CONSTRUCTOR_CLOSURE", "RUNTIME_TEMPLATE", "INITIAL_PROJECTION", "MUTATING_ABI", "NONPROXY_OPCODE"]) console.log(`DEPLOYMENT_${name}=PASS`);
console.log("DEPLOYMENT_MEMBER_CODE=UNRESTRICTED_CALLBACK_SEMANTIC_LEMMA_SEPARATE");
console.log("DEPLOYMENT_ADMISSION=PASS");