import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, parseEther } from "viem";

const ZERO = 0n;
const ONE = parseEther("1");
const TWO = parseEther("2");
const THREE = parseEther("3");
const FOUR = parseEther("4");

type Credits = readonly [bigint, bigint, bigint, bigint, bigint, bigint, bigint];
type MemberSet = readonly [number, number, number, number];

const RECEIPT_PATH = "results/receipt_bridge.receipt.v1.json";

function serialiseLogs(logs: readonly { address: string; data: string; topics: readonly string[] }[]) {
  return logs.map((log) => ({
    address: log.address,
    data: log.data,
    topics: [...log.topics],
  }));
}

describe("receipt-gated threshold bridge capture", () => {
  it("records a real successful OPE receipt and a real underpayment revert", async () => {
    const connection = await network.create();
    const { viem } = connection;
    const publicClient = await viem.getPublicClient();
    const wallets = await viem.getWalletClients();
    const [poolController, buyer, ...rest] = wallets;
    const memberWallets = rest.slice(0, 7);
    const memberAddresses = memberWallets.map((wallet) => wallet.account.address) as [
      `0x${string}`,
      `0x${string}`,
      `0x${string}`,
      `0x${string}`,
      `0x${string}`,
      `0x${string}`,
      `0x${string}`,
    ];

    const contract = await viem.deployContract("OverlappingPoolEscrow", [
      poolController.account.address,
      memberAddresses,
    ]);
    const bytecode = await publicClient.getBytecode({ address: contract.address });
    assert.ok(bytecode, "deployed contract must have runtime bytecode");

    const credits: Credits = [TWO, ZERO, ZERO, ZERO, TWO, ZERO, ZERO];
    const selectedMemberIndices: MemberSet = [0, 1, 4, 5];
    const configureHash = await contract.write.configureCredits([credits], {
      account: poolController.account,
      value: FOUR,
    });
    const configureReceipt = await publicClient.waitForTransactionReceipt({ hash: configureHash });

    const quote = await contract.read.quoteFour([selectedMemberIndices]);
    assert.equal(quote, FOUR);

    let underpaymentError = "";
    try {
      await contract.write.acquireFour([selectedMemberIndices], {
        account: buyer.account,
        value: THREE,
      });
    } catch (error) {
      underpaymentError = error instanceof Error ? error.name : String(error);
    }
    assert.notEqual(underpaymentError, "", "the underpayment must be rejected by the contract");
    assert.equal(await contract.read.completed(), false);

    const acquireHash = await contract.write.acquireFour([selectedMemberIndices], {
      account: buyer.account,
      value: quote,
    });
    const acquireReceipt = await publicClient.waitForTransactionReceipt({ hash: acquireHash });
    const acquireTransaction = await publicClient.getTransaction({ hash: acquireHash });
    const chainId = await publicClient.getChainId();

    assert.equal(acquireReceipt.status, "success");
    assert.equal(acquireTransaction.from.toLowerCase(), buyer.account.address.toLowerCase());
    assert.equal(acquireTransaction.to?.toLowerCase(), contract.address.toLowerCase());
    assert.equal(acquireTransaction.value, FOUR);
    assert.equal(await contract.read.completed(), true);
    assert.equal(await contract.read.deliveredShareMask(), 51);
    assert.equal(await contract.read.terminalMask(), 51);
    assert.equal((await contract.read.acquirer()).toLowerCase(), buyer.account.address.toLowerCase());

    const result = {
      schema: "ope-receipt-bridge-capture/v1",
      chain_id: chainId,
      contract: {
        address: contract.address,
        runtime_bytecode_keccak256: keccak256(bytecode),
      },
      committee_member_addresses: memberAddresses,
      configure_transaction: {
        hash: configureHash,
        status: configureReceipt.status,
        block_number: configureReceipt.blockNumber.toString(),
        value_wei: FOUR.toString(),
      },
      payment_transaction: {
        hash: acquireHash,
        status: acquireReceipt.status,
        block_number: acquireReceipt.blockNumber.toString(),
        from: acquireTransaction.from,
        to: acquireTransaction.to,
        value_wei: acquireTransaction.value.toString(),
        logs: serialiseLogs(acquireReceipt.logs),
      },
      ope_state_after_payment: {
        configured: await contract.read.configured(),
        completed: await contract.read.completed(),
        acquirer: await contract.read.acquirer(),
        delivered_share_mask: Number(await contract.read.deliveredShareMask()),
        terminal_mask: Number(await contract.read.terminalMask()),
        total_acquisition_call_value_wei: (await contract.read.totalAcquisitionCallValue()).toString(),
        selected_member_indices: [...selectedMemberIndices],
        quote_wei: quote.toString(),
      },
      negative_underpayment: {
        attempted_value_wei: THREE.toString(),
        reverted: underpaymentError !== "",
        error_name: underpaymentError,
        state_remained_incomplete_before_success: true,
      },
      binding_rule: "member_index i maps to paid-threshold operator_id i+1; bridge verifies a public operator signature over this mapping",
    };

    await mkdir("results", { recursive: true });
    await writeFile(RECEIPT_PATH, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  });
});
