import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { describe, it } from "node:test";

import { network } from "hardhat";
import {
  keccak256,
  parseEther,
  recoverMessageAddress,
} from "viem";

const OUTPUT = "results/ope_process_routes.v1.json";
const UPDATE = process.env.UPDATE_OPE_PROCESS_CAPTURE === "1";
const CONFIRMATIONS = 6;
const ZERO = 0n;
const TWO = parseEther("2");
const FOUR = parseEther("4");

type Credits = readonly [bigint, bigint, bigint, bigint, bigint, bigint, bigint];
type MemberSet = readonly [number, number, number, number];

function fourMemberSets(): MemberSet[] {
  const result: MemberSet[] = [];
  for (let a = 0; a < 7; a += 1)
    for (let b = a + 1; b < 7; b += 1)
      for (let c = b + 1; c < 7; c += 1)
        for (let d = c + 1; d < 7; d += 1)
          result.push([a, b, c, d]);
  return result;
}

function authMessage(input: {
  chainId: number;
  contractAddress: string;
  paymentTxHash: string;
  buyer: string;
  selectedMemberIndices: MemberSet;
  quoteWei: bigint;
}): string {
  return [
    "THRESHCERT-OPE-PROCESS-AUTH-V1",
    input.chainId,
    input.contractAddress.toLowerCase(),
    input.paymentTxHash.toLowerCase(),
    input.buyer.toLowerCase(),
    input.selectedMemberIndices.join(","),
    input.quoteWei.toString(),
    "threshold-capability-v16",
  ].join("|");
}

describe("OPE controlled positive process capture", () => {
  it("replays all 35 fixed-configuration routes with buyer auth and six confirmations", async () => {
    const connection = await network.create();
    const { viem } = connection;
    const publicClient = await viem.getPublicClient();
    const testClient = await viem.getTestClient();
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
    const credits: Credits = [TWO, ZERO, ZERO, ZERO, TWO, ZERO, ZERO];
    const chainId = await publicClient.getChainId();
    const routes = [];

    for (const selectedMemberIndices of fourMemberSets()) {
      const contract = await viem.deployContract("OverlappingPoolEscrow", [
        poolController.account.address,
        memberAddresses,
      ]);
      const bytecode = await publicClient.getBytecode({ address: contract.address });
      assert.ok(bytecode);

      const configureHash = await contract.write.configureCredits([credits], {
        account: poolController.account,
        value: FOUR,
      });
      const configureReceipt = await publicClient.waitForTransactionReceipt({ hash: configureHash });
      const quote = await contract.read.quoteFour([selectedMemberIndices]);

      const paymentHash = await contract.write.acquireFour([selectedMemberIndices], {
        account: buyer.account,
        value: quote,
      });
      const paymentReceipt = await publicClient.waitForTransactionReceipt({ hash: paymentHash });
      const payment = await publicClient.getTransaction({ hash: paymentHash });
      await testClient.mine({ blocks: CONFIRMATIONS - 1 });
      const observedHead = await publicClient.getBlockNumber();
      const confirmations = Number(observedHead - paymentReceipt.blockNumber + 1n);

      assert.equal(paymentReceipt.status, "success");
      assert.equal(confirmations, CONFIRMATIONS);
      assert.equal(payment.from.toLowerCase(), buyer.account.address.toLowerCase());
      assert.equal(payment.value, quote);
      assert.equal(await contract.read.completed(), true);
      assert.equal(await contract.read.totalAcquisitionCallValue(), quote);
      assert.equal(await contract.read.claimable([buyer.account.address]), 0n);
      await assert.rejects(contract.write.withdraw({ account: buyer.account }));
      await assert.rejects(
        contract.write.acquireFour([selectedMemberIndices], {
          account: buyer.account,
          value: quote,
        }),
      );

      const message = authMessage({
        chainId,
        contractAddress: contract.address,
        paymentTxHash: paymentHash,
        buyer: buyer.account.address,
        selectedMemberIndices,
        quoteWei: quote,
      });
      const signature = await buyer.signMessage({ message });
      const recovered = await recoverMessageAddress({ message, signature });
      assert.equal(recovered.toLowerCase(), buyer.account.address.toLowerCase());

      const mask = selectedMemberIndices.reduce((value, index) => value | (1 << index), 0);
      assert.equal(await contract.read.terminalMask(), mask);
      assert.equal(await contract.read.deliveredShareMask(), mask);

      routes.push({
        route_id: `ope-${selectedMemberIndices.join("-")}`,
        selected_member_indices: [...selectedMemberIndices],
        selected_operator_ids: selectedMemberIndices.map((index) => index + 1),
        contract: {
          address: contract.address,
          runtime_bytecode_keccak256: keccak256(bytecode),
        },
        configure_transaction: {
          hash: configureHash,
          status: configureReceipt.status,
          block_number: configureReceipt.blockNumber.toString(),
          value_wei: FOUR.toString(),
        },
        payment_transaction: {
          hash: paymentHash,
          status: paymentReceipt.status,
          block_number: paymentReceipt.blockNumber.toString(),
          from: payment.from,
          to: payment.to,
          value_wei: payment.value.toString(),
        },
        finality: {
          policy_confirmations: CONFIRMATIONS,
          observed_head_block: observedHead.toString(),
          observed_confirmations: confirmations,
        },
        request_authentication: {
          scheme: "EIP-191/secp256k1",
          message,
          signature,
          recovered_signer: recovered,
        },
        terminal_state: {
          completed: await contract.read.completed(),
          acquirer: await contract.read.acquirer(),
          delivered_share_mask: Number(await contract.read.deliveredShareMask()),
          terminal_mask: Number(await contract.read.terminalMask()),
          buyer_claimable_wei: (await contract.read.claimable([buyer.account.address])).toString(),
          total_acquisition_call_value_wei: (await contract.read.totalAcquisitionCallValue()).toString(),
        },
        single_use: {
          second_acquire_rejected: true,
          buyer_withdraw_rejected: true,
        },
      });
    }

    assert.equal(routes.length, 35);
    const result = {
      schema: "ope-controlled-process-routes/v1",
      chain_id: chainId,
      scope: {
        configuration_credits_units: [2, 0, 0, 0, 2, 0, 0],
        accounting_unit: "native call value / 10^18 wei",
        gas_excluded: true,
        resource: "threshold-capability-v16",
        first_success_ends_at_commitment_valid_plaintext_delivery: true,
      },
      roles: {
        attacker: buyer.account.address,
        service_contract_controller: poolController.account.address,
        committee_member_addresses: memberAddresses,
      },
      route_count: routes.length,
      minimum_contract_cost_units: Math.min(
        ...routes.map((route) => Number(BigInt(route.payment_transaction.value_wei) / parseEther("1"))),
      ),
      maximum_contract_cost_units: Math.max(
        ...routes.map((route) => Number(BigInt(route.payment_transaction.value_wei) / parseEther("1"))),
      ),
      routes,
    };
    const rendered = `${JSON.stringify(result, null, 2)}\n`;
    if (UPDATE) {
      await mkdir("results", { recursive: true });
      await writeFile(OUTPUT, rendered, "utf8");
    } else {
      const committed = await readFile(OUTPUT, "utf8");
      assert.equal(committed, rendered);
    }
  });
});
