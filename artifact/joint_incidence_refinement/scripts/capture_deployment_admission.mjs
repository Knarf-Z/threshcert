import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ARTIFACT_PATH = path.join(ROOT, "artifacts", "contracts", "OverlappingPoolEscrow.sol", "OverlappingPoolEscrow.json");
const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1]);
const rpcUrl = args.get("--rpc") ?? process.env.ADMISSION_RPC_URL;
const txHash = args.get("--tx") ?? process.env.ADMISSION_DEPLOYMENT_TX;
const output = path.resolve(args.get("--out") ?? path.join(ROOT, "results", "deployment_admission_public.json"));
if (!rpcUrl || !txHash) throw new Error("usage: node scripts/capture_deployment_admission.mjs --rpc URL --tx 0xHASH [--out FILE]");
if (!/^0x[0-9a-fA-F]{64}$/.test(txHash)) throw new Error("bad deployment transaction hash");
let requestId = 0;
async function rpc(method, params) {
  const response = await fetch(rpcUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: ++requestId, method, params }),
  });
  if (!response.ok) throw new Error(`${method}: HTTP ${response.status}`);
  const body = await response.json();
  if (body.error) throw new Error(`${method}: ${body.error.message}`);
  return body.result;
}
const artifactBytes = await readFile(ARTIFACT_PATH);
const artifact = JSON.parse(artifactBytes);
const tx = await rpc("eth_getTransactionByHash", [txHash]);
const receipt = await rpc("eth_getTransactionReceipt", [txHash]);
if (!tx || !receipt) throw new Error("deployment transaction or receipt unavailable");
if (tx.to !== null || receipt.status !== "0x1" || !receipt.contractAddress) throw new Error("not a successful direct creation transaction");
const block = await rpc("eth_getBlockByHash", [receipt.blockHash, true]);
if (!block) throw new Error("deployment block unavailable");
const transactions = block.transactions.map((x) => typeof x === "string" ? x : x.hash);
if (transactions.at(-1)?.toLowerCase() !== txHash.toLowerCase()) throw new Error("deployment must be final transaction in block for block-end initial-state observations");
const blockTag = receipt.blockNumber;
const runtimeCode = await rpc("eth_getCode", [receipt.contractAddress, blockTag]);
const chainIdHex = await rpc("eth_chainId", []);
const creation = artifact.bytecode.toLowerCase();
if (!tx.input.toLowerCase().startsWith(creation)) throw new Error("creation bytecode prefix mismatch");
const encoded = tx.input.slice(creation.length);
if (encoded.length !== 8 * 64) throw new Error("unexpected constructor encoding length");
const words = Array.from({ length: 8 }, (_, i) => encoded.slice(i * 64, (i + 1) * 64));
const decodeAddress = (word) => `0x${word.slice(24)}`;
const controller = decodeAddress(words[0]);
const members = words.slice(1).map(decodeAddress);
const buildDir = path.join(ROOT, "artifacts", "build-info");
const outputFiles = (await readdir(buildDir)).filter((x) => x.endsWith(".output.json"));
let methodIdentifiers;
for (const file of outputFiles) {
  const build = JSON.parse(await readFile(path.join(buildDir, file), "utf8"));
  for (const [source, contracts] of Object.entries(build.output?.contracts ?? {})) {
    const contract = contracts.OverlappingPoolEscrow;
    if (source.endsWith("OverlappingPoolEscrow.sol") && contract) methodIdentifiers = contract.evm.methodIdentifiers;
  }
}
if (!methodIdentifiers) throw new Error("method identifiers unavailable");
const word = (x) => BigInt(x).toString(16).padStart(64, "0");
const call = async (signature, suffix = "") => {
  const selector = methodIdentifiers[signature];
  if (!selector) throw new Error(`selector unavailable: ${signature}`);
  return rpc("eth_call", [{ to: receipt.contractAddress, data: `0x${selector}${suffix}` }, blockTag]);
};
const decodeUint = (x) => BigInt(x).toString();
const decodeBool = (x) => BigInt(x) !== 0n;
const observedMembers = [];
const memberCode = [];
const credits = [];
const shareOwners = [];
for (let i = 0; i < 7; i += 1) {
  observedMembers.push(decodeAddress((await call("members(uint256)", word(i))).slice(2).padStart(64, "0")));
  credits.push(decodeUint(await call("credits(uint256)", word(i))));
  shareOwners.push(decodeAddress((await call("shareOwner(uint256)", word(i))).slice(2).padStart(64, "0")));
  memberCode.push(await rpc("eth_getCode", [members[i], blockTag]));
}
const record = {
  schema: "overlapping-pool-deployment-admission/v1",
  compiler: {
    version: "0.8.28",
    evmRevision: "cancun",
    artifactSha256: createHash("sha256").update(artifactBytes).digest("hex"),
  },
  chain: {
    chainId: Number(BigInt(chainIdHex)),
    blockNumber: BigInt(block.number).toString(),
    blockHash: block.hash,
    transactionHashes: transactions,
  },
  deployment: {
    transactionHash: tx.hash,
    transactionIndex: Number(BigInt(receipt.transactionIndex)),
    from: tx.from,
    to: tx.to,
    input: tx.input,
    receiptStatus: "success",
    receiptBlockHash: receipt.blockHash,
    receiptBlockNumber: BigInt(receipt.blockNumber).toString(),
    contractAddress: receipt.contractAddress,
  },
  constructor: { controller, members },
  runtime: {
    code: runtimeCode,
    sha256: createHash("sha256").update(Buffer.from(runtimeCode.slice(2), "hex")).digest("hex"),
    immutableReferences: artifact.immutableReferences,
  },
  observationsAtDeploymentBlock: {
    poolController: decodeAddress((await call("poolController()")).slice(2).padStart(64, "0")),
    members: observedMembers,
    memberCode,
    configured: decodeBool(await call("configured()")),
    completed: decodeBool(await call("completed()")),
    terminalMask: Number(BigInt(await call("terminalMask()"))),
    deliveredShareMask: Number(BigInt(await call("deliveredShareMask()"))),
    totalAcquisitionCallValue: decodeUint(await call("totalAcquisitionCallValue()")),
    acquirer: decodeAddress((await call("acquirer()")).slice(2).padStart(64, "0")),
    credits,
    shareOwners,
    balance: BigInt(await rpc("eth_getBalance", [receipt.contractAddress, blockTag])).toString(),
  },
};
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify(record, null, 2)}\n`, "utf8");
console.log(`DEPLOYMENT_ADMISSION_RECORD=${output}`);
console.log(`DEPLOYMENT_ADMISSION_BLOCK=${record.chain.blockNumber}:${record.chain.blockHash}`);
console.log(`DEPLOYMENT_ADMISSION_CONTRACT=${record.deployment.contractAddress}`);