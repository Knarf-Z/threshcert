import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const OUTPUT = path.join(ROOT, "data", "capture.public.v1.json");
const ETH_RPC = process.env.ETH_AUDIT_RPC_URL ?? "https://ethereum-rpc.publicnode.com";
const GNOSIS_RPC = process.env.GNOSIS_AUDIT_RPC_URL ?? "https://rpc.gnosischain.com";

const SSV_PROXY = "0xDD9BC35aE942eF0cFa76930954a156B3fF30a4E1";
const TBTC_PROXY = "0x46d52E41C2F300BC82217Ce22b920c34995204eb";
const SHUTTER_MANAGER = "0x7C2337f9bFce19d8970661DA50dE8DD7d3D34abb";
const SHUTTER_SET10 = "0xE817E77109e2E6a8025eB30dB3542eC18bBDE828";
const DRAND_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971";

const TOPICS = {
  dkgSubmitted: "0x8e7fd4293d7db11807147d8890c287fad3396fbb09a4e92273fc7856076c153a",
  dkgApproved: "0xe6e9d5eba171e82025efb3f3d44fd35905e7283d104284cb9f3bbc5bf1e4276f",
  walletCreated: "0xbe8f27cef1f3d94120c9c547c3614f5b992fdb0c0a497cc920fde06546291ab4",
  walletClosed: "0xa6ae4af610b8ada39d3675190ead27a5552631a8e33f53e4e37dbb082f11a73e",
};

function sha(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function bytecodeRecord(hex) {
  if (typeof hex !== "string" || !hex.startsWith("0x")) throw new Error("bad bytecode");
  const raw = Buffer.from(hex.slice(2), "hex");
  return { bytes: raw.length, sha256: sha(raw) };
}

async function getBytes(url) {
  const response = await fetch(url, { headers: { accept: "application/json,text/html;q=0.8" } });
  const bytes = Buffer.from(await response.arrayBuffer());
  return { response, bytes };
}

async function getJson(url) {
  const { response, bytes } = await getBytes(url);
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return { value: JSON.parse(bytes.toString("utf8")), sha256: sha(bytes), bytes: bytes.length };
}

async function rpc(url, method, params) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  if (!response.ok) throw new Error(`${response.status} ${method}`);
  const body = await response.json();
  if (body.error) throw new Error(`${method}: ${JSON.stringify(body.error)}`);
  return body.result;
}

function unwrap(value) {
  if (Array.isArray(value)) return value.map(unwrap);
  if (value && typeof value === "object" && Object.hasOwn(value, "value")) return unwrap(value.value);
  return value;
}

function parameter(log, name) {
  const found = log.decoded?.parameters?.find((item) => item.name === name);
  if (!found) throw new Error(`missing decoded parameter ${name}`);
  return unwrap(found.value);
}

async function contractCapture(address, blockHex) {
  const metadataUrl = `https://eth.blockscout.com/api/v2/smart-contracts/${address}`;
  const metadata = await getJson(metadataUrl);
  const proxyCode = await rpc(ETH_RPC, "eth_getCode", [address, blockHex]);
  const implementations = [];
  for (const item of metadata.value.implementations ?? []) {
    const implementationCode = await rpc(ETH_RPC, "eth_getCode", [item.address_hash, blockHex]);
    implementations.push({
      address: item.address_hash,
      name: item.name ?? null,
      runtime: bytecodeRecord(implementationCode),
    });
  }
  return {
    address,
    proxyType: metadata.value.proxy_type ?? null,
    runtime: bytecodeRecord(proxyCode),
    implementations,
    metadataSource: { url: metadataUrl, sha256: metadata.sha256, bytes: metadata.bytes },
  };
}

async function captureSsv(blockHex) {
  const first = await getJson("https://api.ssv.network/api/v4/mainnet/clusters?page=1&perPage=100");
  const pages = Number(first.value.pagination.pages);
  const clusters = [...first.value.clusters];
  const pageDigests = [{ page: 1, sha256: first.sha256, bytes: first.bytes }];
  for (let page = 2; page <= pages; page += 1) {
    const item = await getJson(`https://api.ssv.network/api/v4/mainnet/clusters?page=${page}&perPage=100`);
    clusters.push(...item.value.clusters);
    pageDigests.push({ page, sha256: item.sha256, bytes: item.bytes });
  }
  const eligible = clusters
    .filter((c) => c.active === true && c.isLiquidated === false && Array.isArray(c.operators) && c.operators.length === 4)
    .sort((a, b) => a.clusterId.localeCompare(b.clusterId));
  if (eligible.length === 0) throw new Error("no eligible SSV cluster");
  const selected = eligible[0];
  return {
    contract: await contractCapture(SSV_PROXY, blockHex),
    api: {
      endpoint: "https://api.ssv.network/api/v4/mainnet/clusters",
      returnedClusters: clusters.length,
      eligibleClusters: eligible.length,
      pageDigests,
    },
    committee: {
      selectionRule: "lexicographically smallest active nonliquidated four-operator cluster in the complete captured API result",
      clusterId: selected.clusterId,
      ownerAddress: selected.ownerAddress,
      operators: selected.operators.map(Number),
      threshold: 3,
      validatorCount: Number(selected.validatorCount),
      recordBlockNumber: Number(selected.blockNumber),
      active: selected.active,
      liquidated: selected.isLiquidated,
    },
  };
}

async function blockscoutLogs(topic) {
  const url = `https://eth.blockscout.com/api/v2/addresses/${TBTC_PROXY}/logs?topic=${topic}`;
  const result = await getJson(url);
  return { ...result, url };
}

async function captureTbtc(blockHex) {
  const [created, closed, submitted, approved] = await Promise.all([
    blockscoutLogs(TOPICS.walletCreated),
    blockscoutLogs(TOPICS.walletClosed),
    blockscoutLogs(TOPICS.dkgSubmitted),
    blockscoutLogs(TOPICS.dkgApproved),
  ]);
  if (closed.value.next_page_params) throw new Error("wallet-closure page incomplete");
  const closedIds = new Set(closed.value.items.map((item) => item.topics[1].toLowerCase()));
  const activeCreated = created.value.items.find((item) => !closedIds.has(item.topics[1].toLowerCase()));
  if (!activeCreated) throw new Error("no approved nonclosed tBTC wallet on first creation page");
  const walletId = activeCreated.topics[1];
  const resultHash = activeCreated.topics[2];
  const submittedLog = submitted.value.items.find((item) => item.topics[1].toLowerCase() === resultHash.toLowerCase());
  const approvedLog = approved.value.items.find((item) => item.topics[1].toLowerCase() === resultHash.toLowerCase());
  if (!submittedLog || !approvedLog) throw new Error("missing tBTC DKG pair");
  const result = parameter(submittedLog, "result");
  if (!Array.isArray(result) || !Array.isArray(result[5]) || result[5].length !== 100) {
    throw new Error("unexpected tBTC DKG result shape");
  }
  return {
    contract: await contractCapture(TBTC_PROXY, blockHex),
    committee: {
      selectionRule: "highest-block WalletCreated record not present in the complete WalletClosed result at capture",
      walletId,
      resultHash,
      threshold: 51,
      members: result[5].map(Number),
      misbehavedMemberIndices: result[2].map(Number),
      membersHash: result[6],
      groupPublicKey: result[1],
      submitted: {
        blockNumber: Number(submittedLog.block_number),
        blockHash: submittedLog.block_hash,
        transactionHash: submittedLog.transaction_hash,
      },
      approved: {
        blockNumber: Number(approvedLog.block_number),
        blockHash: approvedLog.block_hash,
        transactionHash: approvedLog.transaction_hash,
      },
      created: {
        blockNumber: Number(activeCreated.block_number),
        blockHash: activeCreated.block_hash,
        transactionHash: activeCreated.transaction_hash,
      },
    },
    indexSources: [created, closed, submitted, approved].map((x) => ({
      url: x.url,
      sha256: x.sha256,
      bytes: x.bytes,
    })),
  };
}

async function captureShutter() {
  const sourcePath = path.join(ROOT, "..", "production_snapshot", "data", "shutter_keyper_snapshot.json");
  const bytes = await readFile(sourcePath);
  const snapshot = JSON.parse(bytes.toString("utf8"));
  const blockHex = `0x${Number(snapshot.archival_block_number).toString(16)}`;
  const [managerCode, setCode] = await Promise.all([
    rpc(GNOSIS_RPC, "eth_getCode", [SHUTTER_MANAGER, blockHex]),
    rpc(GNOSIS_RPC, "eth_getCode", [SHUTTER_SET10, blockHex]),
  ]);
  return {
    snapshotSource: { path: "../production_snapshot/data/shutter_keyper_snapshot.json", sha256: sha(bytes), bytes: bytes.length },
    blockNumber: snapshot.archival_block_number,
    blockHash: snapshot.archival_block_hash,
    chainId: snapshot.chain_id,
    manager: { address: SHUTTER_MANAGER, runtime: bytecodeRecord(managerCode) },
    set: { address: SHUTTER_SET10, runtime: bytecodeRecord(setCode) },
    committee: {
      threshold: snapshot.threshold_count,
      members: snapshot.member_addresses,
    },
  };
}

async function captureDrand() {
  const infoUrl = `https://api.drand.sh/v2/chains/${DRAND_HASH}/info`;
  const latestUrl = `https://api.drand.sh/v2/chains/${DRAND_HASH}/rounds/latest`;
  const [info, latest] = await Promise.all([getJson(infoUrl), getJson(latestUrl)]);
  return {
    chainInfo: info.value,
    latestRound: latest.value,
    sources: [
      { url: infoUrl, sha256: info.sha256, bytes: info.bytes },
      { url: latestUrl, sha256: latest.sha256, bytes: latest.bytes },
    ],
    committee: {
      threshold: null,
      members: null,
      status: "NOT_EXPOSED_BY_OFFICIAL_PUBLIC_CLIENT_INFO_ENDPOINT",
    },
  };
}

async function sourceDigests(urls) {
  const records = [];
  for (const url of urls) {
    try {
      const { response, bytes } = await getBytes(url);
      records.push({ url, status: response.status, sha256: sha(bytes), bytes: bytes.length });
    } catch (error) {
      records.push({ url, status: "FETCH_ERROR", error: String(error) });
    }
  }
  return records;
}

const finalized = await rpc(ETH_RPC, "eth_getBlockByNumber", ["finalized", false]);
const blockHex = finalized.number;
const officialSources = await sourceDigests([
  "https://docs.gnosischain.com/shutterized-gc/DeployedContracts",
  "https://docs.gnosischain.com/shutterized-gc/",
  "https://docs.ssv.network/developers/smart-contracts",
  "https://docs.ssv.network/developers/security/",
  "https://docs.ssv.network/developers/tools/ssv-subgraph/subgraph-examples",
  "https://docs.threshold.network/contract-addresses/tbtc",
  "https://docs.threshold.network/applications/tbtc-v2/wallet-signing",
  "https://docs.threshold.network/app-development/tbtc-contracts-api/ecdsa-api/walletregistry",
  "https://docs.drand.love/developer/",
  "https://docs.drand.love/docs/specification/",
]);

const output = {
  schema: "threshold-deployment-public-capture/v1",
  capturedAt: new Date().toISOString(),
  cutoffDate: "2026-08-03",
  ethereumFinalizedBlock: {
    number: Number.parseInt(finalized.number, 16),
    hash: finalized.hash,
    timestamp: Number.parseInt(finalized.timestamp, 16),
  },
  officialSourceDigests: officialSources,
  systems: {
    "gnosis-shutter-set10": await captureShutter(),
    "ssv-mainnet-cluster": await captureSsv(blockHex),
    "tbtc-v2-mainnet-wallet": await captureTbtc(blockHex),
    "drand-quicknet": await captureDrand(),
  },
};

await mkdir(path.dirname(OUTPUT), { recursive: true });
await writeFile(OUTPUT, `${JSON.stringify(output, null, 2)}\n`, "utf8");
console.log(`CAPTURED_SYSTEMS=${Object.keys(output.systems).length}`);
console.log(`ETHEREUM_FINALIZED_BLOCK=${output.ethereumFinalizedBlock.number}`);
console.log(`OUTPUT=${OUTPUT}`);

