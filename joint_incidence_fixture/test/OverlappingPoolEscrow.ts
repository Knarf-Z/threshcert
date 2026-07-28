import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { parseEther } from "viem";

const ZERO = 0n;
const ONE = parseEther("1");
const TWO = parseEther("2");
const FOUR = parseEther("4");
const EIGHT = parseEther("8");

type Credits = readonly [bigint, bigint, bigint, bigint, bigint, bigint, bigint];
type MemberSet = readonly [number, number, number, number];

function fourMemberSets(): MemberSet[] {
  const result: MemberSet[] = [];
  for (let a = 0; a < 7; a += 1) {
    for (let b = a + 1; b < 7; b += 1) {
      for (let c = b + 1; c < 7; c += 1) {
        for (let d = c + 1; d < 7; d += 1) {
          result.push([a, b, c, d]);
        }
      }
    }
  }
  return result;
}

function discreteFeasibleStates(): Credits[] {
  const values = [ZERO, ONE, TWO];
  const states: Credits[] = [];

  for (const y0 of values)
    for (const y1 of values)
      for (const y2 of values)
        for (const y3 of values)
          for (const y4 of values)
            for (const y5 of values)
              for (const y6 of values) {
                const candidate: Credits = [y0, y1, y2, y3, y4, y5, y6];
                const firstPool = y0 + y1 + y2 + y3;
                const secondPool = y3 + y4 + y5 + y6;
                if (firstPool <= TWO && secondPool <= TWO) {
                  states.push(candidate);
                }
              }

  return states;
}

function allDiscreteStates(): Credits[] {
  const values = [ZERO, ONE, TWO];
  const states: Credits[] = [];

  for (const y0 of values)
    for (const y1 of values)
      for (const y2 of values)
        for (const y3 of values)
          for (const y4 of values)
            for (const y5 of values)
              for (const y6 of values)
                states.push([y0, y1, y2, y3, y4, y5, y6]);

  return states;
}

function isFeasible(state: Credits): boolean {
  return (
    state[0] + state[1] + state[2] + state[3] <= TWO &&
    state[3] + state[4] + state[5] + state[6] <= TWO
  );
}

async function setup() {
  const connection = await network.create();
  const { viem } = connection;
  const publicClient = await viem.getPublicClient();
  const wallets = await viem.getWalletClients();
  const [poolController, attacker, ...rest] = wallets;
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

  return {
    contract,
    publicClient,
    poolController,
    attacker,
    memberWallets,
  };
}

describe("OverlappingPoolEscrow residual-price fixture", () => {
  it("checks the complete 117-by-35 discrete state-set grid", async () => {
    const fixture = await setup();
    const states = discreteFeasibleStates();
    const sets = fourMemberSets();

    assert.equal(states.length, 117);
    assert.equal(sets.length, 35);

    const coordinateMaxima = Array<bigint>(7).fill(0n);
    let minimum = EIGHT;
    let checked = 0;

    for (const state of states) {
      for (let i = 0; i < 7; i += 1) {
        if (state[i] > coordinateMaxima[i]) coordinateMaxima[i] = state[i];
      }
      for (const memberSet of sets) {
        const quote = await fixture.contract.read.quoteCandidate([
          state,
          memberSet,
        ]);
        const expected = memberSet.reduce(
          (sum, memberIndex) => sum + TWO - state[memberIndex],
          ZERO,
        );
        assert.equal(quote, expected);
        assert.ok(quote >= FOUR);
        if (quote < minimum) minimum = quote;
        checked += 1;
      }
    }

    assert.equal(checked, 4_095);
    assert.equal(minimum, FOUR);
    assert.deepEqual(coordinateMaxima, Array<bigint>(7).fill(TWO));
  });

  it("accepts exactly 117 of the 2,187 integer credit states", async () => {
    const fixture = await setup();
    const canonicalSet: MemberSet = [0, 1, 2, 3];
    let accepted = 0;
    let rejected = 0;

    for (const state of allDiscreteStates()) {
      if (isFeasible(state)) {
        await fixture.contract.read.quoteCandidate([state, canonicalSet]);
        accepted += 1;
      } else {
        await assert.rejects(
          fixture.contract.read.quoteCandidate([state, canonicalSet]),
        );
        rejected += 1;
      }
    }

    assert.equal(accepted, 117);
    assert.equal(rejected, 2_070);
  });

  it("realizes the exact four-unit minimizing execution", async () => {
    const fixture = await setup();
    const credits: Credits = [TWO, ZERO, ZERO, ZERO, TWO, ZERO, ZERO];
    const minimizingSet: MemberSet = [0, 1, 4, 5];

    await fixture.contract.write.configureCredits([credits], {
      account: fixture.poolController.account,
      value: FOUR,
    });

    assert.equal(await fixture.contract.read.quoteFour([minimizingSet]), FOUR);

    await fixture.contract.write.acquireFour([minimizingSet], {
      account: fixture.attacker.account,
      value: FOUR,
    });

    assert.equal(await fixture.contract.read.completed(), true);
    assert.equal(await fixture.contract.read.totalAttackerPayment(), FOUR);
    assert.equal(
      await fixture.publicClient.getBalance({ address: fixture.contract.address }),
      EIGHT,
    );

    for (const index of minimizingSet) {
      assert.equal(
        await fixture.contract.read.claimable([
          fixture.memberWallets[index].account.address,
        ]),
        TWO,
      );
    }
  });

  it("rejects cap violations, fractional credits, and duplicate sets", async () => {
    const fixture = await setup();
    const invalidCredits: Credits = [TWO, ONE, ZERO, ZERO, ZERO, ZERO, ZERO];
    const fractionalCredits: Credits = [
      parseEther("0.5"),
      ZERO,
      ZERO,
      ZERO,
      ZERO,
      ZERO,
      ZERO,
    ];
    const validCredits: Credits = [TWO, ZERO, ZERO, ZERO, TWO, ZERO, ZERO];

    await assert.rejects(
      fixture.contract.write.configureCredits([invalidCredits], {
        account: fixture.poolController.account,
        value: parseEther("3"),
      }),
    );

    await assert.rejects(
      fixture.contract.write.configureCredits([fractionalCredits], {
        account: fixture.poolController.account,
        value: parseEther("0.5"),
      }),
    );

    await fixture.contract.write.configureCredits([validCredits], {
      account: fixture.poolController.account,
      value: FOUR,
    });

    await assert.rejects(
      fixture.contract.read.quoteFour([[0, 0, 4, 5]]),
    );
  });
});
