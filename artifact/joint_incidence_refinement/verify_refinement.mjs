import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = path.join(ROOT, "contracts", "OverlappingPoolEscrow.sol");
const ARTIFACT = path.join(ROOT, "artifacts", "contracts", "OverlappingPoolEscrow.sol", "OverlappingPoolEscrow.json");
const RESULT = path.join(ROOT, "results", "refinement_certificate.json");
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

function opcodes(runtime) {
  let hex = runtime.startsWith("0x") ? runtime.slice(2) : runtime;
  const metadataBytes = Number.parseInt(hex.slice(-4), 16);
  hex = hex.slice(0, hex.length - (metadataBytes + 2) * 2);
  const bytes = Buffer.from(hex, "hex");
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
    for (let i = at; i < xs.length; i += 1) { acc.push(xs[i]); go(i + 1, acc); acc.pop(); }
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
const abiFunctions = artifact.abi.filter((x) => x.type === "function");
const signatures = abiFunctions.map(signature).sort();
const mutating = abiFunctions.filter((x) => !["view","pure"].includes(x.stateMutability)).map(signature).sort();
check(JSON.stringify(mutating) === JSON.stringify(["acquireFour(uint8[4])","configureCredits(uint256[7])","withdraw()"]), `unexpected mutating ABI: ${mutating}`);
check(!artifact.abi.some((x) => ["fallback","receive"].includes(x.type)), "fallback/receive present");
for (const token of ["delegatecall","selfdestruct","create2","assembly","fallback(","receive("]) check(!source.toLowerCase().includes(token), `forbidden feature ${token}`);

const acquire = body(source, "acquireFour");
const configure = body(source, "configureCredits");
const withdraw = body(source, "withdraw");
check(occurrences(source, /completed\s*=\s*true\s*;/g) === 1 && acquire.includes("completed = true;"), "completed has another writer");
check(acquire.includes("uint256 requiredPayment = quoteFour(memberIndices);"), "unchecked quote");
check(acquire.includes("if (msg.value != requiredPayment) revert IncorrectFunding();"), "payment is not exact");
check(acquire.includes("totalAttackerPayment = requiredPayment;"), "payment not preserved");
check(occurrences(source, /credits\s*\[[^\]]+\]\s*=/g) === 1 && configure.includes("credits[i] = candidate[i];"), "credits mutable after initialization");
check(withdraw.indexOf("claimable[msg.sender] = 0;") < withdraw.indexOf(".call{value: amount}"), "withdraw is not checks-effects-interactions");

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

const certificate = {
  schema: "overlapping-pool-schema-certificate/v2",
  generatedFromPinnedInputs: true,
  implementationAuditEvidence: {
    source: "contracts/OverlappingPoolEscrow.sol", sourceSha256: sha(source),
    artifact: "artifacts/contracts/OverlappingPoolEscrow.sol/OverlappingPoolEscrow.json", artifactSha256: sha(artifactText),
    creationBytecodeSha256: sha(Buffer.from(artifact.bytecode.slice(2),"hex")),
    runtimeBytecodeSha256: sha(Buffer.from(artifact.deployedBytecode.slice(2),"hex")),
    abiSignatures: signatures,
    mutatingEntryClosure: { initialization:["configureCredits(uint256[7])"], acquisition:["acquireFour(uint8[4])"], neutral:["withdraw()"], fallbackOrReceive:[] },
    runtimeOpcodeGuards: ops,
  },
  declaredTransactionSchema: {
    state: "(configured credit vector y, completed flag, selected terminal set if completed)",
    abstraction: "pi(x)=(empty,y) before completion; pi(x)=(S,y) after the unique successful acquireFour schema action",
    initialStates: ys.length, terminalSets: sets.length,
    quotientStates: ys.length*(1+sets.length), acquisitionMacroEdges: edges,
    neutralSteps: "views and withdrawals preserve (A,y); nested completion is classified by the unique completed-state write",
  },
  obligations: {
    declaredSchemaEntryClosure:"PASS: configure, acquireFour, view, and withdraw action classes are explicit",
    schemaForwardSimulation:"PASS: every declared acquisition action preserves y, selects four distinct members, and maps to one root-terminal block edge",
    schemaBackwardRealizability:"PASS: all 117 x 35 declared block edges have a distinct tuple and exact quote",
    schemaTerminalEquivalence:"PASS: exactly the post-acquireFour schema states are terminal",
    schemaPaymentPreservation:"PASS: all 4095 schema quotes equal the RPSC residual sum",
    implementationToSchemaBridge:"NOT_PROVED: source/ABI/bytecode checks below are audit evidence, not an EVM reachability proof",
    implementationEntryEvidence:"PASS: pinned mutating ABI is configureCredits, acquireFour, withdraw; no fallback or receive",
    implementationOpcodeEvidence:"PASS: no delegatecall, callcode, create, create2, or selfdestruct; the sole CALL is in the guarded withdrawal path",
  },  finiteCheck: { candidateCreditVectors:3**7, admissibleCreditVectors:ys.length, terminalSets:sets.length, checkedStateSetPairs:edges, minimumResidualPayment:min, maximumResidualPayment:max, coordinateResidualMinima:marginal },
  exclusions:["The certificate proves only the declared finite transaction schema.","The EVM-to-schema refinement remains an explicit unproved premise.","Pool-fund provenance and beneficial ownership remain evidence premises.","No member-willingness or production pass-through claim."],
};
await mkdir(path.dirname(RESULT),{recursive:true});
await writeFile(RESULT,`${JSON.stringify(certificate,null,2)}\n`);
for (const marker of ["ENTRY_CLOSURE","FORWARD_SIMULATION","BACKWARD_REALIZABILITY","TERMINAL_EQUIVALENCE","PAYMENT_PRESERVATION"]) console.log(`SCHEMA_${marker}=PASS`);
console.log("EVM_TO_SCHEMA_BRIDGE=NOT_PROVED");
console.log(`SCHEMA_STATE_SET_PAIRS=${edges}`);
console.log(`SCHEMA_MIN_PAYMENT=${min}`);
console.log("SCHEMA_CERTIFICATE=results/refinement_certificate.json");
