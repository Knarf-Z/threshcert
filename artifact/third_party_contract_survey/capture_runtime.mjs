import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1]);
const rpcUrl = args.get("--rpc");
const address = args.get("--address")?.toLowerCase();
const output = args.get("--out");
const requestedBlock = args.get("--block") ?? "latest";
const deploymentTx = args.get("--deployment-tx");
if (!rpcUrl || !/^0x[0-9a-f]{40}$/.test(address ?? "") || !output) {
  throw new Error("usage: node capture_runtime.mjs --rpc URL --address 0x... --out RECORD.json [--block NUMBER|latest] [--deployment-tx 0x...]");
}

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

const blockTag = requestedBlock === "latest" ? "latest" : `0x${BigInt(requestedBlock).toString(16)}`;
const block = await rpc("eth_getBlockByNumber", [blockTag, false]);
if (!block) throw new Error("block unavailable");
const pinnedTag = block.number;
const runtime = await rpc("eth_getCode", [address, pinnedTag]);
if (runtime === "0x") throw new Error("address has no runtime code at pinned block");
const chainId = Number(BigInt(await rpc("eth_chainId", [])));
const slots = {
  implementation: "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",
  admin: "0xb53127684a568b3173ae13b9f8a6016e0195a4f92e15a6226c98ad8b5d6103",
  beacon: "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50",
};
const proxySlots = {};
for (const [name, slot] of Object.entries(slots)) proxySlots[name] = await rpc("eth_getStorageAt", [address, slot, pinnedTag]);
let deployment;
if (deploymentTx) {
  const tx = await rpc("eth_getTransactionByHash", [deploymentTx]);
  const receipt = await rpc("eth_getTransactionReceipt", [deploymentTx]);
  if (!tx || !receipt) throw new Error("deployment transaction unavailable");
  deployment = {
    transactionHash: tx.hash,
    from: tx.from,
    to: tx.to,
    input: tx.input,
    receiptStatus: receipt.status === "0x1" ? "success" : "reverted",
    receiptBlockNumber: BigInt(receipt.blockNumber).toString(),
    receiptBlockHash: receipt.blockHash,
    contractAddress: receipt.contractAddress,
  };
  if (receipt.contractAddress?.toLowerCase() !== address) throw new Error("deployment receipt address mismatch");
}
const record = {
  schema: "third-party-runtime-record/v1",
  subject: { address },
  chain: {
    chainId,
    blockNumber: BigInt(block.number).toString(),
    blockHash: block.hash,
  },
  deployment,
  runtime: {
    code: runtime,
    sha256: createHash("sha256").update(Buffer.from(runtime.slice(2), "hex")).digest("hex"),
  },
  proxySlots,
};
await mkdir(path.dirname(path.resolve(output)), { recursive: true });
await writeFile(path.resolve(output), `${JSON.stringify(record, null, 2)}\n`, "utf8");
console.log(`CHAIN_BLOCK=${chainId}:${record.chain.blockNumber}:${record.chain.blockHash}`);
console.log(`CONTRACT=${address}`);
console.log(`RECORD=${path.resolve(output)}`);
