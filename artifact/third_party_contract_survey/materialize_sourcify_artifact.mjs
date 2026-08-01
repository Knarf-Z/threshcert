import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1]);
const input = args.get("--input");
const output = args.get("--out");
if (!input || !output) {
  throw new Error("usage: node materialize_sourcify_artifact.mjs --input SOURCIFY.json --out ARTIFACT.json");
}

const response = JSON.parse(await readFile(path.resolve(input), "utf8"));
if (!response.abi || !response.creationBytecode?.recompiledBytecode || !response.runtimeBytecode?.recompiledBytecode) {
  throw new Error("Sourcify response has no complete verified ABI and bytecode pair");
}

const withPrefix = (value) => value.startsWith("0x") ? value : `0x${value}`;
const artifact = {
  schema: "sourcify-derived-solc-artifact/v1",
  provenance: {
    chainId: response.chainId,
    address: response.address,
    match: response.match,
    creationMatch: response.creationMatch,
    runtimeMatch: response.runtimeMatch,
    verifiedAt: response.verifiedAt,
    compilerVersion: response.compilation?.compilerVersion,
    contractName: response.compilation?.name,
    sourceUrl: `https://sourcify.dev/server/v2/contract/${response.chainId}/${response.address}?fields=all`,
  },
  abi: response.abi,
  bytecode: {
    object: withPrefix(response.creationBytecode.recompiledBytecode),
    linkReferences: response.creationBytecode.linkReferences ?? {},
  },
  deployedBytecode: {
    object: withPrefix(response.runtimeBytecode.recompiledBytecode),
    immutableReferences: response.runtimeBytecode.immutableReferences ?? {},
    linkReferences: response.runtimeBytecode.linkReferences ?? {},
  },
  immutableReferences: response.runtimeBytecode.immutableReferences ?? {},
  deployedLinkReferences: response.runtimeBytecode.linkReferences ?? {},
};

await mkdir(path.dirname(path.resolve(output)), { recursive: true });
await writeFile(path.resolve(output), `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
console.log(`ARTIFACT=${path.resolve(output)}`);
console.log(`CONTRACT=${artifact.provenance.contractName}`);
console.log(`MATCH=${artifact.provenance.match}`);
