import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = path.join(ROOT, "contracts", "OverlappingPoolEscrow.sol");
const ARTIFACT = path.join(ROOT, "artifacts", "contracts", "OverlappingPoolEscrow.sol", "OverlappingPoolEscrow.json");
const HARNESS = path.join(ROOT, "formal", "OverlappingPoolEscrowBridge.t.sol");
const FOUNDRY_CONFIG = path.join(ROOT, "foundry.toml");
const HALMOS_RESULT = path.join(ROOT, "results", "halmos_evm_bridge.json");
const HALMOS_RUNNER = path.join(ROOT, "scripts", "run_halmos_bridge.py");
const HALMOS_LOG = path.join(ROOT, "results", "halmos_evm_bridge.log");
const DEPLOYMENT_RECORD = path.join(ROOT, "results", "deployment_admission_local.json");
const DEPLOYMENT_CERTIFICATE = path.join(ROOT, "results", "deployment_admission_certificate.json");
const DEPLOYMENT_NEGATIVE = path.join(ROOT, "results", "deployment_admission_negative.json");
const DEPLOYMENT_CHECKER = path.join(ROOT, "verify_deployment_admission.mjs");
const RESULT = path.join(ROOT, "results", "refinement_certificate.json");
const OBLIGATION_MAP = path.join(ROOT, "results", "refinement_obligation_map.json");
const sha = (x) => createHash("sha256").update(x).digest("hex");
const check = (x, m) => { if (!x) throw new Error(m); };
const occurrences = (s, r) => [...s.matchAll(r)].length;

function body(source, name) {
  const start = source.indexOf(`function ${name}`);
  check(start >= 0, `missing function ${name}`);
  const open = source.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === "{") depth += 1;
    if (source[i] === "}" && --depth === 0) return source.slice(open + 1, i);
  }
  throw new Error(`unterminated function ${name}`);
}

function executable(runtime) {
  const hex = runtime.startsWith("0x") ? runtime.slice(2) : runtime;
  check(hex.length >= 4, "runtime too short");
  const metadataBytes = Number.parseInt(hex.slice(-4), 16);
  const cut = hex.length - (metadataBytes + 2) * 2;
  check(cut >= 0, "bad Solidity metadata trailer");
  return Buffer.from(hex.slice(0, cut), "hex");
}

function opcodes(runtime) {
  const bytes = executable(runtime);
  const counts = new Map();
  for (let pc = 0; pc < bytes.length; pc += 1) {
    const op = bytes[pc];
    counts.set(op, (counts.get(op) ?? 0) + 1);
    if (op >= 0x60 && op <= 0x7f) pc += op - 0x5f;
  }
  return {
    executableBytes: bytes.length,
    call: counts.get(0xf1) ?? 0,
    callcode: counts.get(0xf2) ?? 0,
    delegatecall: counts.get(0xf4) ?? 0,
    create: counts.get(0xf0) ?? 0,
    create2: counts.get(0xf5) ?? 0,
    selfdestruct: counts.get(0xff) ?? 0,
  };
}

const signature = (x) => `${x.name}(${(x.inputs ?? []).map((v) => v.type).join(",")})`;
function combinations(xs, k) {
  const out = [];
  const go = (at, acc) => {
    if (acc.length === k) return out.push([...acc]);
    for (let i = at; i < xs.length; i += 1) {
      acc.push(xs[i]); go(i + 1, acc); acc.pop();
    }
  };
  go(0, []);
  return out;
}
function creditStates() {
  const out = [];
  for (let code = 0; code < 3 ** 7; code += 1) {
    let n = code; const y = [];
    for (let i = 0; i < 7; i += 1) { y.push(n % 3); n = Math.floor(n / 3); }
    if (y.slice(0, 4).reduce((a,b)=>a+b,0) <= 2 && y.slice(3).reduce((a,b)=>a+b,0) <= 2) out.push(y);
  }
  return out;
}

const source = await readFile(SOURCE, "utf8");
const artifactText = await readFile(ARTIFACT, "utf8");
const artifact = JSON.parse(artifactText);
const harness = await readFile(HARNESS, "utf8");
const foundryConfig = await readFile(FOUNDRY_CONFIG, "utf8");
const halmosText = await readFile(HALMOS_RESULT, "utf8");
const halmosRunnerText = await readFile(HALMOS_RUNNER);
const halmos = JSON.parse(halmosText);
const halmosLog = await readFile(HALMOS_LOG);
const deploymentRecordText = await readFile(DEPLOYMENT_RECORD);
const deploymentCertificateText = await readFile(DEPLOYMENT_CERTIFICATE);
const deploymentNegativeText = await readFile(DEPLOYMENT_NEGATIVE);
const deploymentCheckerText = await readFile(DEPLOYMENT_CHECKER);
const deploymentCertificate = JSON.parse(deploymentCertificateText);
const deploymentNegative = JSON.parse(deploymentNegativeText);
check(deploymentCertificate.schema === "overlapping-pool-deployment-admission-certificate/v1", "bad deployment admission certificate schema");
check(deploymentCertificate.status === "PASS", "deployment admission is not PASS");
check(deploymentCertificate.recordSha256 === sha(deploymentRecordText), "deployment admission record hash mismatch");
check(deploymentCertificate.artifactSha256 === sha(artifactText), "deployment admission artifact hash mismatch");
check(deploymentNegative.schema === "overlapping-pool-deployment-admission-negative/v1", "bad negative admission schema");
check(deploymentNegative.status === "PASS" && deploymentNegative.totalRejected === 10, "deployment admission tamper suite failed");
check(deploymentNegative.canonicalRecordSha256 === sha(deploymentRecordText), "negative suite record hash mismatch");
check(deploymentNegative.checkerSha256 === sha(deploymentCheckerText), "negative suite checker hash mismatch");

const abiFunctions = artifact.abi.filter((x) => x.type === "function");
const signatures = abiFunctions.map(signature).sort();
const mutating = abiFunctions.filter((x) => !["view","pure"].includes(x.stateMutability)).map(signature).sort();
check(JSON.stringify(mutating) === JSON.stringify(["acquireFour(uint8[4])","configureCredits(uint256[7])","withdraw()"]), `unexpected mutating ABI: ${mutating}`);
check(!artifact.abi.some((x) => ["fallback","receive"].includes(x.type)), "fallback/receive present");
for (const token of ["delegatecall","selfdestruct","create2","assembly","fallback(","receive("]) {
  check(!source.toLowerCase().includes(token), `forbidden feature ${token}`);
}

const acquire = body(source, "acquireFour");
const configure = body(source, "configureCredits");
const withdraw = body(source, "withdraw");
const validateSet = body(source, "_validateMemberSet");
for (const name of ["configureCredits", "acquireFour", "withdraw"]) {
  const header = source.slice(source.indexOf(`function ${name}`), source.indexOf("{", source.indexOf(`function ${name}`)));
  check(header.includes("nonReentrant"), `${name} lacks nonReentrant`);
}
check(occurrences(source, /completed\s*=\s*true\s*;/g) === 1 && acquire.includes("completed = true;"), "completed has another writer");
check(occurrences(source, /terminalMask\s*=\s*mask\s*;/g) === 1 && acquire.includes("terminalMask = mask;"), "terminal mask has another writer");
check(occurrences(source, /deliveredShareMask\s*=\s*mask\s*;/g) === 1 && acquire.includes("deliveredShareMask = mask;"), "delivered-share mask has another writer");
check(occurrences(source, /shareOwner\s*\[[^\]]+\]\s*=/g) === 2, "shareOwner writer closure mismatch");
check(acquire.includes("shareOwner[memberIndex] = msg.sender;"), "selected share right is not transferred to the payer");
check(acquire.includes("uint256 requiredPayment = quoteFour(memberIndices);"), "unchecked quote");
check(acquire.includes("if (msg.value != requiredPayment) revert IncorrectFunding();"), "payment is not exact");
check(acquire.includes("totalAcquisitionCallValue = requiredPayment;"), "payment not preserved");
check(occurrences(source, /acquirer\s*=\s*msg\.sender\s*;/g) === 1 && acquire.includes("acquirer = msg.sender;"), "acquirer has another writer or is not bound to msg.sender");
check(occurrences(source, /credits\s*\[[^\]]+\]\s*=/g) === 1 && configure.includes("credits[i] = candidate[i];"), "credits mutable after initialization");
check(validateSet.includes("memberIndices[i] >= COMMITTEE_SIZE"), "member range closure absent");
check(validateSet.includes("memberIndices[i] <= memberIndices[i - 1]"), "canonical increasing tuple closure absent");
check(withdraw.indexOf("claimable[msg.sender] = 0;") < withdraw.indexOf(".call{value: amount}"), "withdraw is not checks-effects-interactions");
for (const token of ["configured", "completed", "terminalMask", "deliveredShareMask", "totalAcquisitionCallValue", "acquirer", "credits", "shareOwner"]) {
  check(!withdraw.includes(token), `withdraw reads or writes projection field ${token}`);
}
check(acquire.indexOf("if (completed)") < acquire.indexOf("quoteFour(memberIndices)"), "completed guard does not precede tuple/value-dependent quote");
check(acquire.indexOf("if (!_isExternalAcquirer(msg.sender))") < acquire.indexOf("quoteFour(memberIndices)"), "role-separation guard does not precede tuple/value-dependent quote");
check(source.includes("if (committee[i] == controller) revert ConflictingRole();"), "constructor does not separate controller from members");
check(configure.indexOf("if (configured)") < configure.indexOf("_validateCredits(candidate)"), "reconfiguration guard does not precede candidate/value validation");
check(configure.indexOf("if (msg.sender != poolController)") < configure.indexOf("_validateCredits(candidate)"), "authorization guard does not precede candidate/value validation");
check(occurrences(source, /entered\s*=\s*true\s*;/g) === 1, "bad reentrancy entry guard");
check(occurrences(source, /entered\s*=\s*false\s*;/g) === 1, "bad reentrancy exit guard");
check(occurrences(acquire, /claimable\s*\[/g) === 1, "acquire depends on a hidden claimable-fiber read");
check(acquire.includes("claimable[member] += directPayment;"), "acquire claimable update is not the declared additive credit");
check(!acquire.includes(".call{") && !acquire.includes("delegatecall") && !acquire.includes("callcode"), "acquire performs an external call");
const configureProof = body(harness, "check_EVMConfigureSuccessClosure");
for (const required of [
  "assert(escrow.totalAcquisitionCallValue() == 0);",
  "assert(escrow.acquirer() == address(0));",
  "assert(escrow.deliveredShareMask() == 0);",
  "assert(address(escrow).balance == suppliedValue);",
  "assert(escrow.claimable(_member(i)) == y[i]);",
  "assert(escrow.shareOwner(i) == _member(i));",
]) check(configureProof.includes(required), `configuration proof omits ${required}`);
const edgeProof = body(harness, "_proveEdge");
check(edgeProof.includes("assert(escrow.acquirer() == payer);"), "edge proof omits separated payer binding");
check(edgeProof.includes("assert(escrow.deliveredShareMask() == _mask(selected));"), "edge proof omits delivered-share mask");
check(edgeProof.includes("assert(escrow.shareOwner(i) == expectedOwner);"), "edge proof omits share-right ownership equivalence");
check(edgeProof.includes("assert(escrow.claimable(payer) == 0);"), "edge proof omits zero payer-claimable invariant");
check(occurrences(harness, /function check_EVMEdge_[0-9]+\([^)]*address payer/gs) === 35, "not every edge wrapper quantifies payer");

const hardhatExecutable = executable(artifact.deployedBytecode);
const ops = opcodes(artifact.deployedBytecode);
for (const k of ["callcode","delegatecall","create","create2","selfdestruct"]) check(ops[k] === 0, `runtime contains ${k}`);
check(ops.call === 1, `expected sole CALL in withdraw, found ${ops.call}`);

const ys = creditStates();
const sets = combinations([0,1,2,3,4,5,6], 4);
check(ys.length === 117 && sets.length === 35, `bad finite domains ${ys.length} x ${sets.length}`);
let edges = 0, min = Infinity, max = -Infinity;
const marginal = Array(7).fill(Infinity);
for (const y of ys) {
  for (let i=0;i<7;i+=1) marginal[i]=Math.min(marginal[i],2-y[i]);
  for (const S of sets) {
    const p=S.reduce((z,i)=>z+2-y[i],0);
    check(p>=4, `RPSC floor violated y=${y} S=${S}`);
    min=Math.min(min,p); max=Math.max(max,p); edges+=1;
  }
}
check(edges===4095 && min===4 && marginal.every((x)=>x===0), "finite refinement check failed");

check(halmos.schema === "overlapping-pool-halmos-bridge/v6", "bad Halmos schema");
check(halmos.status === "PASS", "Halmos bridge not PASS");
check(halmos.parameters.halmosLoopBound >= 8, "insufficient Halmos loop bound");
check(halmos.inputs.contractSha256 === sha(source), "Halmos contract hash mismatch");
check(halmos.inputs.harnessSha256 === sha(harness), "Halmos harness hash mismatch");
check(halmos.inputs.foundryConfigSha256 === sha(foundryConfig), "Halmos Foundry config hash mismatch");
check(halmos.transcript.sha256 === sha(halmosLog), "Halmos transcript hash mismatch");
check(halmos.proofCounts.symbolicEdgeWrappers === 35, "bad edge proof count");
check(halmos.proofCounts.symbolicPayerEdgeWrappers === 35, "bad symbolic-payer proof count");
check(halmos.proofCounts.preTerminalWithdrawWrappers === 7, "bad pre-terminal withdraw proof count");
check(halmos.proofCounts.terminalWithdrawWrappers === 21, "bad terminal withdraw proof count");
check(halmos.proofCounts.auxiliaryObligations === 9, "bad auxiliary proof count");
check(halmos.proofCounts.roleConflictObligations === 8, "bad role-conflict proof count");
check(halmos.proofCounts.hostileCallbackObligations === 2, "bad hostile-callback proof count");
check(halmos.proofCounts.totalProofs === 82, "bad total proof count");
check(halmos.proofCounts.failed === 0 && halmos.proofCounts.nonemptyBounds === 0, "Halmos failure or nonempty bound");
const expectedProofs = [
  ...sets.map((s) => `check_EVMEdge_${s.join("")}`),
  ...[0,1,2,3,4,5,6].map((i) => `check_EVMWithdrawProjectionNeutral_${i}`),
  ...["Selected", "SelectedAfterPoolWithdraw", "Unselected"].flatMap(
    (prefix) => [0,1,2,3,4,5,6].map(
      (i) => `check_EVMTerminalWithdraw${prefix}_${i}`
    )
  ),
  "check_EVMCompletedAcquireAlwaysReverts",
  "check_EVMConfigureSuccessClosure", "check_EVMExcessFundingReverts",
  "check_EVMEntryClosure", "check_EVMHostileCallbackPreTerminal",
  "check_EVMHostileCallbackTerminal", "check_EVMInvalidSetReverts",
  "check_EVMOversizeCreditReverts", "check_EVMReconfigureAlwaysReverts",
  "check_EVMRoleConflictedController",
  ...[0,1,2,3,4,5,6].map((i) => `check_EVMRoleConflictedMember_${i}`),
  "check_EVMUnauthorizedConfigure",
  "check_EVMWithdrawValueReverts",
].sort();
check(JSON.stringify(Object.keys(halmos.proofs).sort()) === JSON.stringify(expectedProofs), "Halmos proof-name closure mismatch");
for (const name of expectedProofs) {
  check(Array.isArray(halmos.proofs[name].bounds) && halmos.proofs[name].bounds.length === 0, `${name} has nonempty bounds`);
  check(occurrences(harness, new RegExp(`function ${name}\\b`, "g")) === 1, `${name} wrapper missing or duplicated`);
}
const hardhatExecutableSha = sha(hardhatExecutable);
check(halmos.compiledRuntime.foundryRuntimeExecutableSha256 === hardhatExecutableSha, "Foundry/Hardhat executable bytecode mismatch");
check(halmos.compiledRuntime.foundryRuntimeExecutableBytes === hardhatExecutable.length, "Foundry/Hardhat executable length mismatch");

const bridgeScope = {
  evmRevision: "cancun",
  deployment: "direct creation admitted against the exact runtime template and constructor; controller and seven distinct nonzero members are role-separated; member code is unrestricted, with arbitrary-callee closure relying on EVM call/storage isolation plus the shared lock and concrete hostile receivers checking the mutating-reentry basis",
  initializationPrefix: "from the admitted fresh deployment, each successful controller-only configureCredits(y) is exactly controller-funded and creates one post-configuration root with credits and claimable balances y, initial member-owned share rights, zero delivery/payment masks, zero acquirer, and contract balance sum(y); invalid prefixes revert",
  successUniverse: "the refined LTS starts after a successful one-time configuration and covers every subsequent top-level acquireFour/withdraw call; acquire values span uint256, withdraw is nonpayable, and reverts stutter",
  projection: "on the post-configuration LTS, (credits,completed,terminalMask,deliveredShareMask,totalAcquisitionCallValue); configured is fixed true; acquirer and shareOwner are auxiliary payer/delivery invariants; claimable balances form a projection-neutral fiber",
  closedContractEconomicIncidence: "every successful acquisition is called and exactly funded by an address that is neither controller nor member; it has no claimable balance, refund, rebate, or withdrawal path; controller funds the immutable credit vector; exactly the four selected on-chain share rights move from their members to that payer",
  externalGeneralizationNotClaimed: [
    "off-contract reimbursements or common beneficial ownership among addresses",
    "cryptographic usability or confidentiality of the controlled share-right token",
    "member willingness and production-system pass-through",
  ],
};

const obligationMap = {
  schema: "overlapping-pool-refinement-obligation-map/v1",
  status: "PASS",
  theoremShape: "initial totality for every admissible y; CR1--CR5 refinement; terminal-family completeness for K; trace exactness; then explicit payment-labelled trace--outcome correspondence for mechanism lifting",
  paperClauseMap: {
    CR1: "entryClosure",
    CR2: "forwardSimulation",
    CR3: "backwardRealization",
    CR4: "terminalEquivalence",
    CR5: "paymentPreservation",
    offsetLiftDefinition: "offsetLiftStructure",
    separatePrefixPremise: "initializationTotality",
    separateTerminalPremise: "terminalFamilyCompleteness",
    separateMechanismLiftPremise: "outcomeCompleteness",
  },
  scope: bridgeScope,
  refinementClauses: {
    initializationTotality: {
      status: "PASS",
      evidence: [
        "check_EVMConfigureSuccessClosure (symbolic candidate and value; success iff admissible and exactly funded)",
        "check_EVMOversizeCreditReverts + check_EVMExcessFundingReverts + check_EVMUnauthorizedConfigure",
        "deployment admission role separation plus fresh share-right owner getters",
      ],
    },
    offsetLiftStructure: {
      status: "PASS",
      evidence: [
        "the initial abstract set is exactly the 117 (empty,y) roots",
        "all 4,095 nonstuttering edges preserve y and add one declared four-member block",
        "the terminal abstract set is exactly the 117-by-35 product and there are no offset-changing edges",
      ],
    },
    terminalFamilyCompleteness: {
      status: "PASS",
      evidence: [
        "the declared terminal family is exactly all 35 four-subsets of seven members",
        "tuple validation admits exactly one strictly increasing encoding of each four-subset and rejects every other terminal mask",
        "completed, terminalMask, and deliveredShareMask have their unique writers in acquireFour",
      ],
    },
    outcomeCompleteness: {
      status: "PASS",
      evidence: [
        "the closed-contract mechanism outcome universe is defined as the successful admitted post-configuration EVM traces",
        "entry closure and unique terminal writers make acquireFour the only success-producing transition; pair and payment labels are the same trace observations on both sides",
        "no lift to external willingness, reimbursement, beneficial ownership, or cryptographic usability is claimed",
      ],
    },
    entryClosure: {
      status: "PASS",
      evidence: [
        "exact mutating ABI closure: configureCredits, acquireFour, withdraw",
        "check_EVMEntryClosure + nonpayable-withdraw proof",
        "runtime opcode exclusion of proxy/delegate/create/selfdestruct paths",
      ],
    },
    forwardSimulation: {
      status: "PASS",
      evidence: [
        "35 symbolic canonical-set edge wrappers quantify the role-separated payer and bind terminal/delivery masks, acquirer, zero payer claimable balance, and every share owner",
        "invalid-tuple, wrong-payment, reconfiguration, and completed-replay rejection",
        "source-level storage noninterference checks for the claimable fiber",
      ],
    },
    backwardRealization: {
      status: "PASS",
      evidence: [
        "for each of 35 terminals, symbolic y, full-domain wrongPayment, and symbolic role-separated payer prove exact payment succeeds",
        "acquireFour has no claimable-fiber read and no external call, so the realization is uniform over every reachable source fiber",
      ],
    },
    terminalEquivalence: {
      status: "PASS",
      evidence: [
        "completed, terminalMask, and deliveredShareMask have unique writers in acquireFour",
        "35 symbolic-payer wrappers prove the exact canonical mask, caller binding, and selected/unselected share owners; replay cannot change them",
      ],
    },
    paymentPreservation: {
      status: "PASS",
      evidence: [
        "exact msg.value guard, unique totalAcquisitionCallValue assignment, and unique acquirer=msg.sender binding",
        "eight role-conflict proofs plus source-order checks force the payer outside controller/member withdrawal roles",
        "4,095 finite RPSC equalities and 35 symbolic-y/symbolic-payer EVM edge obligations",
        "withdraw cannot read or write projection fields",
      ],
    },
    closedContractEconomicIncidence: {
      status: "PASS",
      evidence: [
        "controller-only exact funding fixes every pool credit and controller/member roles are disjoint",
        "eight Halmos wrappers reject acquisition by the controller or any member for symbolic admissible credit vectors",
        "35 edge wrappers quantify a nonzero controller/member/escrow-separated payer and transfer exactly four member-owned share rights to it",
        "the payer cannot be claimable, acquireFour has no external call, and withdraw pays members only",
      ],
    },
    callbackAndFiberClosure: {
      status: "PASS",
      evidence: [
        "28 per-member withdrawal-class obligations",
        "two concrete hostile receivers reenter every mutating entry in pre-terminal and terminal fibers; EVM call/storage isolation plus the shared lock supplies the arbitrary-callee semantic step",
        "sole CALL is guarded withdraw; no DELEGATECALL/CALLCODE",
      ],
    },
  },
  trustedComputingBase: [
    "Solidity 0.8.28 compiler and Cancun code generation",
    "Foundry/Hardhat compilation and their agreed executable runtime hash",
    "Halmos 0.3.3 symbolic EVM semantics and path exploration",
    "Yices 2.6.4 SMT solving",
    "the runner proof-name/parser closure, harness assumptions, source-level noninterference checks, admission checker, and the EVM call/storage-isolation argument for arbitrary callees",
  ],
  explicitExclusions: [
    "out-of-gas behavior, chain reorganization, non-Cancun execution, and unadmitted creation/runtime",
    "off-contract reimbursement/common beneficial ownership, cryptographic usability of each controlled share right, member willingness, and production pass-through",
  ],
};
const obligationMapText = `${JSON.stringify(obligationMap, null, 2)}\n`;
await mkdir(path.dirname(OBLIGATION_MAP), { recursive: true });
await writeFile(OBLIGATION_MAP, obligationMapText);

const certificate = {
  schema: "overlapping-pool-schema-certificate/v7",
  generatedFromPinnedInputs: true,
  implementationAuditEvidence: {
    source: "contracts/OverlappingPoolEscrow.sol", sourceSha256: sha(source),
    artifact: "artifacts/contracts/OverlappingPoolEscrow.sol/OverlappingPoolEscrow.json", artifactSha256: sha(artifactText),
    creationBytecodeSha256: sha(Buffer.from(artifact.bytecode.slice(2),"hex")),
    runtimeBytecodeSha256: sha(Buffer.from(artifact.deployedBytecode.slice(2),"hex")),
    runtimeExecutableSha256: hardhatExecutableSha,
    runtimeExecutableBytes: hardhatExecutable.length,
halmosCertificate: "results/halmos_evm_bridge.json", halmosCertificateSha256: sha(halmosText),
    halmosRunner: "scripts/run_halmos_bridge.py", halmosRunnerSha256: sha(halmosRunnerText),
    halmosTranscript: "results/halmos_evm_bridge.log", halmosTranscriptSha256: sha(halmosLog),
    deploymentAdmissionRecord: "results/deployment_admission_local.json", deploymentAdmissionRecordSha256: sha(deploymentRecordText),
    deploymentAdmissionCertificate: "results/deployment_admission_certificate.json", deploymentAdmissionCertificateSha256: sha(deploymentCertificateText),
    deploymentAdmissionNegative: "results/deployment_admission_negative.json", deploymentAdmissionNegativeSha256: sha(deploymentNegativeText),
deploymentAdmissionCheckerSha256: sha(deploymentCheckerText),
    refinementObligationMap: "results/refinement_obligation_map.json",
    refinementObligationMapSha256: sha(Buffer.from(obligationMapText)),
    foundryHardhatExecutableMatch: true,
    abiSignatures: signatures,
    mutatingEntryClosure: { initialization:["configureCredits(uint256[7])"], acquisition:["acquireFour(uint8[4])"], neutral:["withdraw()"], fallbackOrReceive:[] },
    runtimeOpcodeGuards: ops,
  },
  bridgeScope,
  declaredTransactionSchema: {
    state: "post-configuration root (credit vector y, member-owned share rights, incomplete) or one completed canonical terminal with four payer-owned share rights; pre-configuration states belong to the separately verified initialization prefix",
    abstraction: "pi(x)=(empty,y) before completion; pi(x)=(S,y) after the unique successful canonical acquireFour action, with terminalMask=deliveredShareMask=S",
    initialStates: ys.length, initializationPrefixes: ys.length, terminalSets: sets.length,
    quotientStates: ys.length*(1+sets.length), acquisitionMacroEdges: edges,
    neutralSteps: "successful/reverting withdrawals preserve pi across pre-terminal and terminal claimable classes; views are observations outside the transition LTS; reconfiguration and acquisition replay revert",
  },
  obligations: {
    declaredSchemaEntryClosure:"PASS: configure, canonical acquire, view, and withdraw action classes are explicit",
    schemaForwardSimulation:"PASS: every declared acquisition preserves y, selects one canonical four-set, and maps root to its terminal",
    schemaBackwardRealizability:"PASS: all 117 x 35 block edges have an exact EVM realization",
    schemaTerminalEquivalence:"PASS: completed, terminalMask, deliveredShareMask, and shareOwner exactly identify the unique post-acquisition terminal and four delivered rights",
    schemaPaymentPreservation:"PASS: all 4095 quotes equal the RPSC residual sum",
    implementationToSchemaBridge:"PASS on the post-configuration LTS under bridgeScope: 82 Halmos proofs, zero failures, and empty exploration bounds",
implementationInitialization:"PASS: every admissible y has an exact controller-funded configuration prefix; credits, claimable balances, member-owned share rights, zero delivery/payment masks, zero acquirer, and escrow balance are checked; invalid prefixes revert",
    implementationEntryClosure:"PASS: symbolic selector, unauthorized/repeated configuration, eight role-conflict wrappers, invalid tuple, completed replay, success-closure, full-value-domain proofs, and a symbolic permitted payer on all 35 terminals",
    implementationCallbackClosure:"PASS under the stated EVM semantic lemma: concrete hostile receivers reenter acquire, configure, and withdraw in both fibers; the shared lock rejects the complete mutating-reentry basis, while Halmos does not quantify over unknown callee bytecode",
    implementationOpcodeClosure:"PASS: no delegatecall, callcode, create, create2, or selfdestruct; sole CALL is guarded withdrawal",
    implementationDeploymentAdmission:"PASS: direct creation input, role-separated constructor arguments, runtime template modulo immutables, initial share-right projection, ABI, and opcode closure are machine checked; ten tampered records are rejected",
    implementationArtifactIdentity:"PASS: pinned source/harness/config hashes and Foundry/Hardhat executable bytecode agree",
  },
  finiteCheck: { candidateCreditVectors:3**7, admissibleCreditVectors:ys.length, terminalSets:sets.length, checkedStateSetPairs:edges, minimumResidualPayment:min, maximumResidualPayment:max, coordinateResidualMinima:marginal },
  exclusions:[
    "The EVM bridge is fixture-specific, not a theorem about arbitrary contracts.",
    "It excludes runtime-template mismatch, an uncertified creation transaction, gas exhaustion, reorganization, and non-Cancun revisions; delegation-style code on a later revision requires a revision-matched admission record.",
    "Within the admitted contract ledger, share-right delivery, exact external payer funding, and controller-funded credits are discharged; off-contract reimbursement/common control and cryptographic usability are not.",
    "No member-willingness, production pass-through, or nonzero production-incidence claim.",
  ],
};
await mkdir(path.dirname(RESULT),{recursive:true});
await writeFile(RESULT,`${JSON.stringify(certificate,null,2)}\n`);
for (const marker of ["ENTRY_CLOSURE","FORWARD_SIMULATION","BACKWARD_REALIZABILITY","TERMINAL_EQUIVALENCE","PAYMENT_PRESERVATION"]) console.log(`SCHEMA_${marker}=PASS`);
console.log("HALMOS_PROOFS=82_PASS_0_FAIL_0_BOUNDS");
console.log("FOUNDRY_HARDHAT_EXECUTABLE_BYTECODE=MATCH");
console.log("DEPLOYMENT_ADMISSION_CERTIFICATE=PASS");
console.log("DEPLOYMENT_ADMISSION_TAMPER_CASES=10_REJECTED");
console.log("HOSTILE_MUTATING_REENTRY_BASIS=PASS");
console.log("ARBITRARY_CALLEE_CLOSURE=EVM_SEMANTIC_LEMMA");
console.log("CONFIGURATION_PREFIX_TOTALITY=PASS");
console.log("OFFSET_LIFT_ROOT_TERMINAL_STRUCTURE=PASS");
console.log("TERMINAL_FAMILY_COMPLETENESS=35_OF_35_PASS");
console.log("CLOSED_CONTRACT_TRACE_OUTCOME_CORRESPONDENCE=PASS");
console.log("POSTCONFIGURATION_EVM_TO_SCHEMA_BRIDGE=PASS");
console.log("EVM_TO_SCHEMA_SCOPE=ADMITTED_CANCUN_RUNTIME_WITH_CLOSED_CONTRACT_INCIDENCE");
console.log(`SCHEMA_STATE_SET_PAIRS=${edges}`);
console.log(`SCHEMA_MIN_PAYMENT=${min}`);
console.log("SCHEMA_CERTIFICATE=results/refinement_certificate.json");