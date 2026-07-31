import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

import { network } from "hardhat";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ARTIFACT = path.join(
  ROOT,
  "artifacts",
  "contracts",
  "OverlappingPoolEscrow.sol",
  "OverlappingPoolEscrow.json",
);
const RESULT = path.join(ROOT, "results", "deployment_admission_local.json");
const sha = (hex: `0x${string}`) =>
  createHash("sha256").update(Buffer.from(hex.slice(2), "hex")).digest("hex");

describe("deployment admission fixture", () => {
  it("captures a direct deployment with pinned runtime and constructor", async () => {
    const connection = await network.create();
    const { viem } = connection;
    const publicClient = await viem.getPublicClient();
    const wallets = await viem.getWalletClients();
    const [controller, ...rest] = wallets;
    const members = rest.slice(0, 7).map((w) => w.account.address) as unknown as readonly [
      `0x${string}`, `0x${string}`, `0x${string}`, `0x${string}`,
      `0x${string}`, `0x${string}`, `0x${string}`,
    ];
    const contract = await viem.deployContract("OverlappingPoolEscrow", [
      controller.account.address,
      members,
    ]);
    const block = await publicClient.getBlock({
      blockTag: "latest",
      includeTransactions: true,
    });
    const deployments = block.transactions.filter((tx) => tx.to === null);
    assert.equal(deployments.length, 1);
    const transaction = deployments[0];
    const receipt = await publicClient.getTransactionReceipt({
      hash: transaction.hash,
    });
    assert.equal(receipt.status, "success");
    assert.equal(receipt.contractAddress?.toLowerCase(), contract.address.toLowerCase());
    const runtimeCode = await publicClient.getCode({
      address: contract.address,
      blockNumber: block.number,
    });
    assert.ok(runtimeCode && runtimeCode !== "0x");
    const artifact = JSON.parse(await readFile(ARTIFACT, "utf8"));
    const observedMembers = [];
    const memberCode = [];
    const credits = [];
    const shareOwners = [];
    for (let i = 0; i < 7; i += 1) {
      observedMembers.push(await contract.read.members([BigInt(i)]));
      credits.push((await contract.read.credits([BigInt(i)])).toString());
      shareOwners.push(await contract.read.shareOwner([BigInt(i)]));
      memberCode.push(await publicClient.getCode({
        address: members[i],
        blockNumber: block.number,
      }) ?? "0x");
    }
    const record = {
      schema: "overlapping-pool-deployment-admission/v1",
      compiler: {
        version: "0.8.28",
        evmRevision: "cancun",
        artifactSha256: createHash("sha256")
          .update(await readFile(ARTIFACT))
          .digest("hex"),
      },
      chain: {
        chainId: await publicClient.getChainId(),
        blockNumber: block.number.toString(),
        blockHash: block.hash,
        transactionHashes: block.transactions.map((tx) => tx.hash),
      },
      deployment: {
        transactionHash: transaction.hash,
        transactionIndex: Number(receipt.transactionIndex),
        from: transaction.from,
        to: transaction.to,
        input: transaction.input,
        receiptStatus: receipt.status,
        receiptBlockHash: receipt.blockHash,
        receiptBlockNumber: receipt.blockNumber.toString(),
        contractAddress: receipt.contractAddress,
      },
      constructor: {
        controller: controller.account.address,
        members,
      },
      runtime: {
        code: runtimeCode,
        sha256: sha(runtimeCode),
        immutableReferences: artifact.immutableReferences,
      },
      observationsAtDeploymentBlock: {
        poolController: await contract.read.poolController(),
        members: observedMembers,
        memberCode,
        configured: await contract.read.configured(),
        completed: await contract.read.completed(),
        terminalMask: Number(await contract.read.terminalMask()),
        deliveredShareMask: Number(await contract.read.deliveredShareMask()),
        totalAcquisitionCallValue: (
          await contract.read.totalAcquisitionCallValue()
        ).toString(),
        acquirer: await contract.read.acquirer(),
        credits,
        shareOwners,
        balance: (
          await publicClient.getBalance({
            address: contract.address,
            blockNumber: block.number,
          })
        ).toString(),
      },
    };
    await mkdir(path.dirname(RESULT), { recursive: true });
    await writeFile(RESULT, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  });
});