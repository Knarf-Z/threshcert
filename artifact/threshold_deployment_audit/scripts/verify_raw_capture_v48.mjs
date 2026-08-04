import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const RAW = path.join(ROOT, "data", "raw_v48");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const parse = (bytes) => JSON.parse(bytes.toString("utf8").replace(/^\uFEFF/, ""));
async function verifyIndex(name, requireJson = false) {
  const entries = parse(await readFile(path.join(RAW, name)));
  const verified = [];
  for (const entry of entries) {
    const absolute = path.resolve(ROOT, entry.path);
    const relative = path.relative(ROOT, absolute);
    if (relative.startsWith("..") || path.isAbsolute(relative)) throw new Error(`${name}: path escape`);
    const bytes = await readFile(absolute);
    if (bytes.length !== entry.bytes || sha(bytes) !== entry.sha256) throw new Error(`${entry.path}: raw hash/length mismatch`);
    if (entry.matches_v1 !== (entry.sha256 === entry.v1_sha256)) throw new Error(`${entry.path}: matches_v1 flag mismatch`);
    if (requireJson) parse(bytes);
    verified.push({ path: entry.path, sha256: entry.sha256, bytes: entry.bytes, matchesFrozenV1Digest: entry.matches_v1 });
  }
  return verified;
}
const official = await verifyIndex("official-index.json");
const api = await verifyIndex("api-index.json", true);
const capture = parse(await readFile(path.join(ROOT, "data", "capture.public.v1.json")));
const blockBytes = await readFile(path.join(RAW, "rpc-ethereum-block.json"));
const managerBytes = await readFile(path.join(RAW, "rpc-gnosis-manager-code.json"));
const setBytes = await readFile(path.join(RAW, "rpc-gnosis-set-code.json"));
const block = parse(blockBytes).result;
const managerHex = parse(managerBytes).result;
const setHex = parse(setBytes).result;
const code = (hex) => Buffer.from(hex.slice(2), "hex");
if (Number.parseInt(block.number, 16) !== capture.ethereumFinalizedBlock.number || block.hash !== capture.ethereumFinalizedBlock.hash) throw new Error("Ethereum fixed block mismatch");
const shutter = capture.systems["gnosis-shutter-set10"];
if (code(managerHex).length !== shutter.manager.runtime.bytes || sha(code(managerHex)) !== shutter.manager.runtime.sha256) throw new Error("Gnosis manager raw runtime mismatch");
if (code(setHex).length !== shutter.set.runtime.bytes || sha(code(setHex)) !== shutter.set.runtime.sha256) throw new Error("Gnosis set raw runtime mismatch");
const result = {
  schema: "raw-public-capture-integrity/v48",
  officialFiles: official,
  apiFiles: api,
  rpcFiles: [
    { path: "data/raw_v48/rpc-ethereum-block.json", sha256: sha(blockBytes), assertion: `block ${capture.ethereumFinalizedBlock.number}:${capture.ethereumFinalizedBlock.hash}` },
    { path: "data/raw_v48/rpc-gnosis-manager-code.json", sha256: sha(managerBytes), assertion: `${shutter.manager.runtime.bytes} runtime bytes:${shutter.manager.runtime.sha256}` },
    { path: "data/raw_v48/rpc-gnosis-set-code.json", sha256: sha(setBytes), assertion: `${shutter.set.runtime.bytes} runtime bytes:${shutter.set.runtime.sha256}` }
  ],
  summary: {
    officialFiles: official.length,
    apiFiles: api.length,
    rpcFiles: 3,
    exactFrozenDigestMatches: [...official, ...api].filter((entry) => entry.matchesFrozenV1Digest).length
  },
  limitation: "Raw files are a 2026-08-03 recapture. Dynamic API/document bytes may differ from the earlier frozen v1 digest. The public Ethereum endpoint returned the fixed block but refused later historical eth_getCode calls without a personal archive token; those code bytes remain digest-only in capture.public.v1.json and are not claimed as raw-recaptured here."
};
const output = `${JSON.stringify(result, null, 2)}\n`;
const generated = path.join(ROOT, "results", "raw_capture_integrity.generated.json");
const canonical = path.join(ROOT, "results", "raw_capture_integrity.v48.json");
await writeFile(generated, output, "utf8");
if (process.argv.includes("--freeze")) await writeFile(canonical, output, "utf8");
else if (!(await readFile(canonical)).equals(Buffer.from(output))) throw new Error("raw capture generated/canonical byte mismatch");
console.log(`RAW_OFFICIAL_FILES=${official.length}`);
console.log(`RAW_API_FILES=${api.length}`);
console.log("RAW_RPC_FILES=3");
console.log("RAW_PUBLIC_CAPTURE_INTEGRITY=PASS");