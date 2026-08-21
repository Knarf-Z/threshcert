import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, parseEther, stringToHex } from "viem";

const FIVE = parseEther("5");
const RESOURCE = keccak256(stringToHex("toy-resource-v1"));
const SHARE_A = keccak256(stringToHex("toy-share-a"));
const SHARE_B = keccak256(stringToHex("toy-share-b"));

async function setup() {
  const connection = await network.create();
  const { viem } = connection;
  const publicClient = await viem.getPublicClient();
  const [buyer, memberA, memberB, outsider] = await viem.getWalletClients();
  const exchange = await viem.deployContract("GlobalNamedAcquirerToy", [
    buyer.account.address,
    memberA.account.address,
    memberB.account.address,
  ]);
  return { viem, publicClient, buyer, memberA, memberB, outsider, exchange };
}

async function open(fixture: Awaited<ReturnType<typeof setup>>) {
  await fixture.exchange.write.open([RESOURCE, SHARE_A, SHARE_B], {
    account: fixture.buyer.account,
    value: FIVE,
  });
}

describe("GlobalNamedAcquirerToy finite-world bridge", () => {
  it("requires the named buyer, exact five-ether prefunding, and one opening", async () => {
    const f = await setup();
    await assert.rejects(f.exchange.write.open([RESOURCE, SHARE_A, SHARE_B], {
      account: f.outsider.account,
      value: FIVE,
    }));
    await assert.rejects(f.exchange.write.open([RESOURCE, SHARE_A, SHARE_B], {
      account: f.buyer.account,
      value: parseEther("4"),
    }));
    await open(f);
    await assert.rejects(f.exchange.write.open([RESOURCE, SHARE_A, SHARE_B], {
      account: f.buyer.account,
      value: FIVE,
    }));
  });

  it("rejects zero commitments and non-separated constructor identities", async () => {
    const f = await setup();
    await assert.rejects(f.viem.deployContract("GlobalNamedAcquirerToy", [
      f.buyer.account.address,
      f.buyer.account.address,
      f.memberB.account.address,
    ]));
    await assert.rejects(f.exchange.write.open([RESOURCE, `0x${"00".repeat(32)}`, SHARE_B], {
      account: f.buyer.account,
      value: FIVE,
    }));
    await assert.rejects(
      f.exchange.write.open([RESOURCE, SHARE_A, SHARE_B], { account: f.buyer.account, value: 0n }),
    );
  });

  it("rejects outsider, wrong share, and replay", async () => {
    const f = await setup();
    await open(f);
    await assert.rejects(f.exchange.write.submitShare([SHARE_A], { account: f.outsider.account }));
    await assert.rejects(f.exchange.write.submitShare([SHARE_B], { account: f.memberA.account }));
    await f.exchange.write.submitShare([SHARE_A], { account: f.memberA.account });
    await assert.rejects(f.exchange.write.submitShare([SHARE_A], { account: f.memberA.account }));
  });

  it("binds usable output to both accepted shares in either order", async () => {
    for (const reverse of [false, true]) {
      const f = await setup();
      await open(f);
      const first = reverse ? [f.memberB, SHARE_B] as const : [f.memberA, SHARE_A] as const;
      const second = reverse ? [f.memberA, SHARE_A] as const : [f.memberB, SHARE_B] as const;
      await f.exchange.write.submitShare([first[1]], { account: first[0].account });
      assert.equal(await f.exchange.read.successful(), false);
      assert.equal(await f.exchange.read.usableOutputCommitment(), `0x${"00".repeat(32)}`);
      await f.exchange.write.submitShare([second[1]], { account: second[0].account });
      assert.equal(await f.exchange.read.successful(), true);
      assert.notEqual(await f.exchange.read.usableOutputCommitment(), `0x${"00".repeat(32)}`);
    }
  });

  it("creates exact two- and three-ether member credits with no buyer credit", async () => {
    const f = await setup();
    await open(f);
    await f.exchange.write.submitShare([SHARE_A], { account: f.memberA.account });
    await f.exchange.write.submitShare([SHARE_B], { account: f.memberB.account });
    assert.equal(await f.exchange.read.credit([f.memberA.account.address]), parseEther("2"));
    assert.equal(await f.exchange.read.credit([f.memberB.account.address]), parseEther("3"));
    assert.equal(await f.exchange.read.credit([f.buyer.account.address]), 0n);
    assert.equal(await f.publicClient.getBalance({ address: f.exchange.address }), FIVE);
  });

  it("permits only member withdrawals and never returns value to the buyer", async () => {
    const f = await setup();
    await open(f);
    await f.exchange.write.submitShare([SHARE_A], { account: f.memberA.account });
    await f.exchange.write.submitShare([SHARE_B], { account: f.memberB.account });
    await assert.rejects(f.exchange.write.withdrawCredit({ account: f.buyer.account }));
    const before = await f.publicClient.getBalance({ address: f.exchange.address });
    await f.exchange.write.withdrawCredit({ account: f.memberA.account });
    await f.exchange.write.withdrawCredit({ account: f.memberB.account });
    const after = await f.publicClient.getBalance({ address: f.exchange.address });
    assert.equal(before - after, FIVE);
    assert.equal(after, 0n);
  });
});
