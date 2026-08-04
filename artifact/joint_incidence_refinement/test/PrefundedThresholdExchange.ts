import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, parseEther, stringToHex } from "viem";

const ONE = parseEther("1");
const PROOF = stringToHex("valid-proof");
const COMMITTEE = keccak256(stringToHex("committee-A"));
const COMMITMENT = (index: number) => keccak256(stringToHex(`share-${index}`));

async function setup() {
  const connection = await network.create();
  const { viem } = connection;
  const publicClient = await viem.getPublicClient();
  const wallets = await viem.getWalletClients();
  const [buyer, outsider, ...members] = wallets;
  const registry = await viem.deployContract("MockThresholdSetRegistry");
  const verifier = await viem.deployContract("MockUsableShareVerifier");
  const exchange = await viem.deployContract("PrefundedThresholdExchange", [registry.address, verifier.address]);
  const memberAddresses = members.slice(0, 4).map((x) => x.account.address);
  const amounts = [ONE, 2n * ONE, 3n * ONE, 4n * ONE];
  return { viem, publicClient, buyer, outsider, members: members.slice(0, 4), memberAddresses, amounts, registry, verifier, exchange };
}

async function open(fixture: Awaited<ReturnType<typeof setup>>) {
  const simulation = await fixture.exchange.simulate.openOrder(
    [COMMITTEE, 7n, fixture.memberAddresses, fixture.amounts],
    { account: fixture.buyer.account, value: 10n * ONE },
  );
  await fixture.exchange.write.openOrder(
    [COMMITTEE, 7n, fixture.memberAddresses, fixture.amounts],
    { account: fixture.buyer.account, value: 10n * ONE },
  );
  return simulation.result;
}

describe("PrefundedThresholdExchange positive bridge", () => {
  it("requires exact buyer prefunding and a registry-approved threshold set", async () => {
    const f = await setup();
    await assert.rejects(f.exchange.write.openOrder([COMMITTEE, 7n, f.memberAddresses, f.amounts], { account: f.buyer.account, value: 9n * ONE }));
    await f.registry.write.setAllowed([false]);
    await assert.rejects(f.exchange.write.openOrder([COMMITTEE, 7n, f.memberAddresses, f.amounts], { account: f.buyer.account, value: 10n * ONE }));
  });

  it("rejects buyer-as-member, duplicate members, and zero payment", async () => {
    const f = await setup();
    const withBuyer = [f.buyer.account.address, ...f.memberAddresses.slice(1)];
    await assert.rejects(f.exchange.write.openOrder([COMMITTEE, 7n, withBuyer, f.amounts], { account: f.buyer.account, value: 10n * ONE }));
    const duplicate = [f.memberAddresses[0], f.memberAddresses[0], f.memberAddresses[2], f.memberAddresses[3]];
    await assert.rejects(f.exchange.write.openOrder([COMMITTEE, 7n, duplicate, f.amounts], { account: f.buyer.account, value: 10n * ONE }));
    await assert.rejects(f.exchange.write.openOrder([COMMITTEE, 7n, f.memberAddresses, [0n, 2n * ONE, 3n * ONE, 4n * ONE]], { account: f.buyer.account, value: 9n * ONE }));
  });

  it("rejects outsider, invalid proof, and replay", async () => {
    const f = await setup();
    const orderId = await open(f);
    await assert.rejects(f.exchange.write.submitShare([orderId, COMMITMENT(0), PROOF], { account: f.outsider.account }));
    await assert.rejects(f.exchange.write.submitShare([orderId, COMMITMENT(0), stringToHex("bad")], { account: f.members[0].account }));
    await f.exchange.write.submitShare([orderId, COMMITMENT(0), PROOF], { account: f.members[0].account });
    await assert.rejects(f.exchange.write.submitShare([orderId, COMMITMENT(0), PROOF], { account: f.members[0].account }));
  });

  it("successful acquisition implies the exact prefunded outflow and member credits", async () => {
    const f = await setup();
    const orderId = await open(f);
    assert.equal(await f.publicClient.getBalance({ address: f.exchange.address }), 10n * ONE);
    for (let i = 0; i < 4; i += 1) {
      await f.exchange.write.submitShare([orderId, COMMITMENT(i), PROOF], { account: f.members[i].account });
    }
    const order = await f.exchange.read.orders([orderId]);
    assert.equal(order[3], 4);
    assert.equal(order[5], 10n * ONE);
    assert.equal(order[6], true);
    for (let i = 0; i < 4; i += 1) assert.equal(await f.exchange.read.credit([f.memberAddresses[i]]), f.amounts[i]);
  });

  it("contains no buyer cancellation or refund entry and only members withdraw credits", async () => {
    const f = await setup();
    const orderId = await open(f);
    await assert.rejects(f.exchange.write.withdrawCredit({ account: f.buyer.account }));
    await f.exchange.write.submitShare([orderId, COMMITMENT(0), PROOF], { account: f.members[0].account });
    const before = await f.publicClient.getBalance({ address: f.exchange.address });
    await f.exchange.write.withdrawCredit({ account: f.members[0].account });
    const after = await f.publicClient.getBalance({ address: f.exchange.address });
    assert.equal(before - after, ONE);
    assert.equal(await f.exchange.read.credit([f.memberAddresses[0]]), 0n);
  });
});

