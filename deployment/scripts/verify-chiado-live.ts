import assert from "node:assert/strict";

import {
  createPublicClient,
  decodeEventLog,
  decodeFunctionData,
  encodeAbiParameters,
  http,
  type Abi,
  type Address,
  type Hex,
  type Transaction,
  type TransactionReceipt,
} from "viem";

import { readJson } from "../src/io.js";
import type {
  DeploymentFile,
  JobFile,
  TransactionRecord,
} from "../src/schema.js";

type SlashingFile = {
  schema: "fc-slashing-result-v1";
  chainId: number;
  contract: Address;
  jobId: Hex;
  memberIndex: number;
  keyperAddress: Address;
  shareHash: Hex;
  memberSignatureHash: Hex;
  verifier: Address;
  observedAt: string;
  releaseTime: string;
  certificateBeforeWei: string;
  certificateAfterWei: string;
  transaction: TransactionRecord;
};

type ContractArtifact = {
  abi: Abi;
  bytecode: Hex;
};

type VerifiedTransaction = {
  transaction: Transaction;
  receipt: TransactionReceipt;
};

const DEFAULT_RPC_URL = "https://rpc.chiado.gnosis.gateway.fm";

function normalized(value: string): string {
  return value.toLowerCase();
}

function assertAddress(actual: string, expected: string, label: string): void {
  assert.equal(normalized(actual), normalized(expected), label);
}

function assertHex(actual: string, expected: string, label: string): void {
  assert.equal(normalized(actual), normalized(expected), label);
}

async function main(): Promise<void> {
  const rpcUrl = process.env.CHIADO_RPC_URL?.trim() || DEFAULT_RPC_URL;
  const deployment = await readJson<DeploymentFile>(
    "results/deployment-chiado.json",
  );
  const job = await readJson<JobFile>("results/job-chiado.json");
  const slashing = await readJson<SlashingFile>(
    "results/slashing-chiado.json",
  );
  const artifact = await readJson<ContractArtifact>(
    "artifacts/contracts/BondedKeyperSlasher.sol/BondedKeyperSlasher.json",
  );

  assert.equal(deployment.schema, "fc-bonded-keyper-deployment-v1");
  assert.equal(job.schema, "fc-release-job-v1");
  assert.equal(slashing.schema, "fc-slashing-result-v1");
  assert.equal(job.chainId, deployment.chainId);
  assert.equal(slashing.chainId, deployment.chainId);
  assertAddress(job.contract, deployment.contract, "job contract mismatch");
  assertAddress(
    slashing.contract,
    deployment.contract,
    "slashing contract mismatch",
  );

  const client = createPublicClient({
    transport: http(rpcUrl, { timeout: 30_000 }),
  });
  assert.equal(await client.getChainId(), deployment.chainId, "wrong chain ID");
  const code = await client.getBytecode({ address: deployment.contract });
  assert.ok(code && code !== "0x", "recorded contract has no deployed bytecode");

  async function verifyTransaction(
    label: string,
    record: TransactionRecord,
    expectedTo: Address | null,
    expectedValue = 0n,
  ): Promise<VerifiedTransaction> {
    assert.equal(record.status, "success", `${label}: record is not successful`);
    const [transaction, receipt] = await Promise.all([
      client.getTransaction({ hash: record.hash }),
      client.getTransactionReceipt({ hash: record.hash }),
    ]);
    assert.equal(receipt.status, "success", `${label}: chain receipt failed`);
    assertHex(receipt.transactionHash, record.hash, `${label}: hash mismatch`);
    assert.equal(
      receipt.blockNumber.toString(),
      record.blockNumber,
      `${label}: block number mismatch`,
    );
    assertHex(receipt.blockHash, record.blockHash, `${label}: block hash mismatch`);
    assert.equal(
      receipt.gasUsed.toString(),
      record.gasUsed,
      `${label}: gas-used mismatch`,
    );
    assert.equal(
      receipt.effectiveGasPrice.toString(),
      record.effectiveGasPrice,
      `${label}: gas-price mismatch`,
    );
    assertAddress(transaction.from, deployment.owner, `${label}: sender mismatch`);
    assert.equal(transaction.value, expectedValue, `${label}: value mismatch`);
    if (expectedTo === null) {
      assert.equal(transaction.to, null, `${label}: expected contract creation`);
    } else {
      assert.ok(transaction.to, `${label}: transaction has no recipient`);
      assertAddress(transaction.to, expectedTo, `${label}: recipient mismatch`);
    }
    return { transaction, receipt };
  }

  const deployed = await verifyTransaction(
    "deployment",
    deployment.transactions.deploy,
    null,
  );
  assert.ok(deployed.receipt.contractAddress, "deployment receipt has no contract");
  assertAddress(
    deployed.receipt.contractAddress,
    deployment.contract,
    "created contract mismatch",
  );
  const constructorArguments = encodeAbiParameters(
    [
      { type: "address", name: "initialOwner" },
      { type: "address", name: "evidenceVerifier" },
      { type: "address", name: "penaltyTreasury" },
    ],
    [deployment.owner, deployment.verifier, deployment.treasury],
  );
  const expectedCreationInput = `${artifact.bytecode}${constructorArguments.slice(2)}`;
  assertHex(
    deployed.transaction.input,
    expectedCreationInput,
    "deployment bytecode or constructor arguments mismatch",
  );

  for (const record of deployment.transactions.registrations) {
    const verified = await verifyTransaction(
      `registration[${record.memberIndex}]`,
      record,
      deployment.contract,
      BigInt(deployment.bondWeiPerMember),
    );
    const decoded = decodeFunctionData({
      abi: artifact.abi,
      data: verified.transaction.input,
    });
    assert.equal(decoded.functionName, "registerMember");
    const args = decoded.args as readonly [number, Address];
    assert.equal(Number(args[0]), record.memberIndex, "registered index mismatch");
    assertAddress(
      args[1],
      deployment.keypers[record.memberIndex].address,
      "registered signer mismatch",
    );
  }

  const frozen = await verifyTransaction(
    "committee freeze",
    deployment.transactions.freeze,
    deployment.contract,
  );
  assert.equal(
    decodeFunctionData({ abi: artifact.abi, data: frozen.transaction.input })
      .functionName,
    "freezeCommittee",
  );

  const opened = await verifyTransaction(
    "release job",
    job.transaction,
    deployment.contract,
  );
  const openCall = decodeFunctionData({
    abi: artifact.abi,
    data: opened.transaction.input,
  });
  assert.equal(openCall.functionName, "openRelease");
  const openArgs = openCall.args as readonly [bigint, Hex, bigint];
  assert.equal(openArgs[0].toString(), job.eon, "opened eon mismatch");
  assertHex(openArgs[1], job.identityHash, "opened identity mismatch");
  assert.equal(
    openArgs[2].toString(),
    job.releaseTime,
    "opened release time mismatch",
  );

  const slashed = await verifyTransaction(
    "slashing",
    slashing.transaction,
    deployment.contract,
  );
  const slashCall = decodeFunctionData({
    abi: artifact.abi,
    data: slashed.transaction.input,
  });
  assert.equal(slashCall.functionName, "slashEarlyShare");
  const slashArgs = slashCall.args as readonly [Hex, number, Hex, Hex, Hex];
  assertHex(slashArgs[0], slashing.jobId, "slashed job mismatch");
  assert.equal(Number(slashArgs[1]), slashing.memberIndex, "member mismatch");
  assertHex(slashArgs[2], slashing.shareHash, "share hash mismatch");
  assertHex(
    slashArgs[3],
    slashing.memberSignatureHash,
    "member-signature hash mismatch",
  );

  let eventArgs:
    | {
        jobId: Hex;
        memberIndex: number;
        shareHash: Hex;
        memberSignatureHash: Hex;
        observedAt: bigint;
        amount: bigint;
      }
    | undefined;
  for (const log of slashed.receipt.logs) {
    try {
      const decoded = decodeEventLog({
        abi: artifact.abi,
        data: log.data,
        topics: log.topics,
      });
      if (decoded.eventName === "EarlyShareSlashed") {
        eventArgs = decoded.args as unknown as NonNullable<typeof eventArgs>;
        break;
      }
    } catch {
      // Ignore logs emitted by contracts outside this artifact ABI.
    }
  }
  assert.ok(eventArgs, "EarlyShareSlashed event not found");
  assertHex(eventArgs.jobId, slashing.jobId, "event job mismatch");
  assert.equal(
    Number(eventArgs.memberIndex),
    slashing.memberIndex,
    "event member mismatch",
  );
  assertHex(eventArgs.shareHash, slashing.shareHash, "event share mismatch");
  assertHex(
    eventArgs.memberSignatureHash,
    slashing.memberSignatureHash,
    "event signature mismatch",
  );
  assert.equal(
    eventArgs.observedAt.toString(),
    slashing.observedAt,
    "event observation time mismatch",
  );
  assert.equal(
    eventArgs.amount.toString(),
    deployment.bondWeiPerMember,
    "event penalty amount mismatch",
  );

  async function readContract(functionName: string, args: readonly unknown[] = []) {
    return client.readContract({
      address: deployment.contract,
      abi: artifact.abi,
      functionName,
      args,
    } as never);
  }

  assert.equal(Number(await readContract("COMMITTEE_SIZE")), 7);
  assert.equal(Number(await readContract("THRESHOLD")), 4);
  assert.equal(Number(await readContract("registeredCount")), 7);
  assert.equal(await readContract("committeeFrozen"), true);
  assertAddress(
    String(await readContract("owner")),
    deployment.owner,
    "live owner mismatch",
  );
  assertAddress(
    String(await readContract("verifier")),
    deployment.verifier,
    "live verifier mismatch",
  );
  assertAddress(
    String(await readContract("treasury")),
    deployment.treasury,
    "live treasury mismatch",
  );
  assert.equal(
    String(await readContract("jobCount")),
    job.nonce,
    "live job count mismatch",
  );

  const bond = BigInt(deployment.bondWeiPerMember);
  for (const keyper of deployment.keypers) {
    const member = (await readContract("members", [BigInt(keyper.index)])) as
      readonly [Address, bigint, boolean, boolean];
    assertAddress(member[0], keyper.address, `member[${keyper.index}] signer`);
    assert.equal(member[2], true, `member[${keyper.index}] not registered`);
    const isSlashed = keyper.index === slashing.memberIndex;
    assert.equal(member[3], isSlashed, `member[${keyper.index}] slash flag`);
    assert.equal(member[1], isSlashed ? 0n : bond, `member[${keyper.index}] bond`);
  }

  const liveJob = (await readContract("jobs", [job.jobId])) as readonly [
    bigint,
    bigint,
    Hex,
    boolean,
  ];
  assert.equal(liveJob[0].toString(), job.eon, "live job eon mismatch");
  assert.equal(
    liveJob[1].toString(),
    job.releaseTime,
    "live job release mismatch",
  );
  assertHex(liveJob[2], job.identityHash, "live job identity mismatch");
  assert.equal(liveJob[3], true, "live job is absent");

  const digest = (await readContract("evidenceDigest", [
    slashing.jobId,
    slashing.memberIndex,
    slashing.shareHash,
    slashing.memberSignatureHash,
  ])) as Hex;
  assert.equal(
    await readContract("usedEvidence", [digest]),
    true,
    "slashing evidence was not marked used",
  );

  const expectedTotalBond = BigInt(deployment.totalBondWei) - bond;
  const liveTotalBond = (await readContract("totalBond")) as bigint;
  const liveCertificate = (await readContract("currentCertificate")) as bigint;
  assert.equal(liveTotalBond, expectedTotalBond, "live total bond mismatch");
  assert.equal(
    liveCertificate.toString(),
    slashing.certificateAfterWei,
    "live certificate mismatch",
  );
  assert.ok(
    (await client.getBalance({ address: deployment.contract })) >= liveTotalBond,
    "contract balance is below its accounted bond",
  );

  console.log(`rpc_url=${rpcUrl}`);
  console.log(`chain_id=${deployment.chainId}`);
  console.log(`contract=${deployment.contract}`);
  console.log("recorded_transactions_verified=11");
  console.log("creation_bytecode_and_constructor=PASS");
  console.log("live_committee_state=PASS");
  console.log(`live_total_bond_wei=${liveTotalBond}`);
  console.log(`live_certificate_wei=${liveCertificate}`);
  console.log("slashing_calldata_and_event=PASS");
  console.log("chiado_live_verification=PASS");
}

main().catch((error: unknown) => {
  console.error("chiado_live_verification=FAIL");
  console.error(error);
  process.exitCode = 1;
});
