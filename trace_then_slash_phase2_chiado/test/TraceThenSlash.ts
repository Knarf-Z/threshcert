import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import {
  keccak256,
  parseEther,
  stringToHex,
  type Hex,
  type WalletClient,
} from "viem";

import {
  signArtifact,
  signVerifierEvidence,
  type EarlyShareArtifact,
} from "../src/evidence.js";

const BOND = parseEther("2");
const CALLER_REWARD = parseEther("0.1");
const EXPECTED_FLOOR = parseEther("8");

type SignedEvidence = EarlyShareArtifact & {
  memberSignature: Hex;
  verifierSignature: Hex;
};

async function setup() {
  const connection = await network.create();
  const { viem, networkHelpers } = connection;
  const publicClient = await viem.getPublicClient();
  const wallets = await viem.getWalletClients();
  const [owner, verifier, treasury, submitter, rewardRecipient, attacker, ...rest] =
    wallets;
  const memberWallets = rest.slice(0, 7);

  const contract = await viem.deployContract("TraceThenSlash", [
    owner.account.address,
    verifier.account.address,
    treasury.account.address,
    CALLER_REWARD,
  ]);

  for (let index = 0; index < memberWallets.length; index += 1) {
    await contract.write.registerMember(
      [index, memberWallets[index].account.address],
      { account: owner.account, value: BOND },
    );
  }
  await contract.write.freezeCommittee({ account: owner.account });

  return {
    contract,
    viem,
    publicClient,
    networkHelpers,
    owner,
    verifier,
    treasury,
    submitter,
    rewardRecipient,
    attacker,
    memberWallets,
  };
}

async function openJob(
  fixture: Awaited<ReturnType<typeof setup>>,
  secondsFromNow = 3_600n,
) {
  const latest = await fixture.publicClient.getBlock();
  const releaseTime = latest.timestamp + secondsFromNow;
  const eon = 1n;
  const identityHash = keccak256(stringToHex("phase1-rq3-instance"));
  await fixture.contract.write.openRelease(
    [eon, identityHash, releaseTime],
    { account: fixture.owner.account },
  );
  const nonce = await fixture.contract.read.jobCount();
  const jobId = await fixture.contract.read.computeJobId([
    eon,
    identityHash,
    releaseTime,
    nonce,
  ]);
  return { jobId, releaseTime };
}

async function makeEvidence(
  fixture: Awaited<ReturnType<typeof setup>>,
  jobId: Hex,
  memberIndex: number,
  options: {
    memberWallet?: WalletClient;
    verifierWallet?: WalletClient;
    label?: string;
  } = {},
): Promise<SignedEvidence> {
  const chainId = await fixture.publicClient.getChainId();
  const artifact: EarlyShareArtifact = {
    jobId,
    memberIndex,
    shareHash: keccak256(
      stringToHex(options.label ?? `covered-early-share-${memberIndex}`),
    ),
  };
  const memberSignature = await signArtifact(
    options.memberWallet ?? fixture.memberWallets[memberIndex],
    chainId,
    fixture.contract.address,
    artifact,
  );
  const verifierSignature = await signVerifierEvidence(
    options.verifierWallet ?? fixture.verifier,
    chainId,
    fixture.contract.address,
    artifact,
    memberSignature,
  );
  return { ...artifact, memberSignature, verifierSignature };
}

function packageArgs(evidence: SignedEvidence[]) {
  return [
    evidence.map((item) => item.jobId),
    evidence.map((item) => item.memberIndex),
    evidence.map((item) => item.shareHash),
    evidence.map((item) => item.memberSignature),
    evidence.map((item) => item.verifierSignature),
  ] as const;
}

function permutations(values: number[]): number[][] {
  if (values.length <= 1) return [values];
  return values.flatMap((value, index) =>
    permutations(values.filter((_, candidate) => candidate !== index)).map(
      (suffix) => [value, ...suffix],
    ),
  );
}

function orderedPartitions(total: number): number[][] {
  if (total === 0) return [[]];
  const partitions: number[][] = [];
  for (let first = 1; first <= total; first += 1) {
    for (const suffix of orderedPartitions(total - first)) {
      partitions.push([first, ...suffix]);
    }
  }
  return partitions;
}

async function slashOne(
  fixture: Awaited<ReturnType<typeof setup>>,
  evidence: SignedEvidence,
) {
  return fixture.contract.write.slashEarlyShare(
    [
      evidence.jobId,
      evidence.memberIndex,
      evidence.shareHash,
      evidence.memberSignature,
      evidence.verifierSignature,
    ],
    { account: fixture.submitter.account },
  );
}

async function assertThresholdOutcome(
  fixture: Awaited<ReturnType<typeof setup>>,
) {
  assert.equal(await fixture.contract.read.frozenThresholdBondFloor(), EXPECTED_FLOOR);
  assert.equal(await fixture.contract.read.currentCertificate(), 0n);
  assert.equal(await fixture.contract.read.totalBond(), parseEther("6"));
  assert.equal(
    await fixture.contract.read.claimableRewards([
      fixture.submitter.account.address,
    ]),
    parseEther("0.4"),
  );
  assert.equal(await fixture.contract.read.treasuryAccrued(), parseEther("7.6"));
}

describe("TraceThenSlash phase-one mechanism", function () {
  it("freezes a 7-member 4-of-7 committee with a positive 8 ETH floor", async function () {
    const fixture = await setup();
    assert.equal(await fixture.contract.read.registeredCount(), 7);
    assert.equal(await fixture.contract.read.totalBond(), parseEther("14"));
    assert.equal(await fixture.contract.read.currentCertificate(), EXPECTED_FLOOR);
    assert.equal(
      await fixture.contract.read.frozenThresholdBondFloor(),
      EXPECTED_FLOOR,
    );
  });

  it("charges the same 8 ETH member loss under four sequential submissions", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    for (let index = 0; index < 4; index += 1) {
      await slashOne(fixture, await makeEvidence(fixture, jobId, index));
    }
    await assertThresholdOutcome(fixture);
  });

  it("atomically charges the same 8 ETH member loss for one threshold package", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence = await Promise.all(
      [0, 1, 2, 3].map((index) => makeEvidence(fixture, jobId, index)),
    );
    await fixture.contract.write.slashPackage(packageArgs(evidence), {
      account: fixture.submitter.account,
    });
    await assertThresholdOutcome(fixture);
  });

  it("charges the same 8 ETH member loss for two repeated packages", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence = await Promise.all(
      [0, 1, 2, 3].map((index) => makeEvidence(fixture, jobId, index)),
    );
    await fixture.contract.write.slashPackage(packageArgs(evidence.slice(0, 2)), {
      account: fixture.submitter.account,
    });
    await fixture.contract.write.slashPackage(packageArgs(evidence.slice(2, 4)), {
      account: fixture.submitter.account,
    });
    await assertThresholdOutcome(fixture);
  });

  it("preserves accounting across the complete 24-by-8 order-partition product", async function () {
    const orders = permutations([0, 1, 2, 3]);
    const partitions = orderedPartitions(4);
    assert.equal(orders.length, 24);
    assert.equal(partitions.length, 8);

    for (const order of orders) {
      for (const partition of partitions) {
        const fixture = await setup();
        const { jobId } = await openJob(fixture);
        const evidence = await Promise.all(
          order.map((index) => makeEvidence(fixture, jobId, index)),
        );
        let offset = 0;
        for (const size of partition) {
          await fixture.contract.write.slashPackage(
            packageArgs(evidence.slice(offset, offset + size)),
            { account: fixture.submitter.account },
          );
          offset += size;
        }
        await assertThresholdOutcome(fixture);
      }
    }
  });

  it("accepts every finite package size 1 through 7 without an external bound b", async function () {
    for (let size = 1; size <= 7; size += 1) {
      const fixture = await setup();
      const { jobId } = await openJob(fixture);
      const evidence = await Promise.all(
        Array.from({ length: size }, (_, index) =>
          makeEvidence(fixture, jobId, index),
        ),
      );
      await fixture.contract.write.slashPackage(packageArgs(evidence), {
        account: fixture.submitter.account,
      });
      assert.equal(
        await fixture.contract.read.totalBond(),
        BOND * BigInt(7 - size),
      );
      assert.equal(
        await fixture.contract.read.claimableRewards([
          fixture.submitter.account.address,
        ]),
        CALLER_REWARD * BigInt(size),
      );
      assert.equal(
        await fixture.contract.read.treasuryAccrued(),
        (BOND - CALLER_REWARD) * BigInt(size),
      );
    }
  });

  it("rolls back an entire package when one verifier signature is forged", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence = await Promise.all(
      [0, 1, 2, 3].map((index) => makeEvidence(fixture, jobId, index)),
    );
    evidence[2] = await makeEvidence(fixture, jobId, 2, {
      verifierWallet: fixture.attacker,
    });

    await assert.rejects(
      fixture.contract.write.slashPackage(packageArgs(evidence), {
        account: fixture.submitter.account,
      }),
      /InvalidVerifierSignature/,
    );
    assert.equal(await fixture.contract.read.totalBond(), parseEther("14"));
    assert.equal(await fixture.contract.read.currentCertificate(), EXPECTED_FLOOR);
    assert.equal(await fixture.contract.read.treasuryAccrued(), 0n);
    assert.equal(
      await fixture.contract.read.claimableRewards([
        fixture.submitter.account.address,
      ]),
      0n,
    );
  });

  it("rejects a verifier-approved artifact signed by the wrong member", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence = await makeEvidence(fixture, jobId, 0, {
      memberWallet: fixture.memberWallets[1],
    });
    await assert.rejects(slashOne(fixture, evidence), /InvalidMemberSignature/);
  });

  it("rejects duplicate members inside an atomic package", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence = await makeEvidence(fixture, jobId, 0);
    await assert.rejects(
      fixture.contract.write.slashPackage(
        packageArgs([evidence, evidence]),
        { account: fixture.submitter.account },
      ),
      /DuplicateMemberInPackage/,
    );
  });

  it("rolls back an atomic package that mixes release jobs", async function () {
    const fixture = await setup();
    const first = await openJob(fixture);
    const second = await openJob(fixture);
    const evidence = [
      await makeEvidence(fixture, first.jobId, 0),
      await makeEvidence(fixture, second.jobId, 1),
    ];
    await assert.rejects(
      fixture.contract.write.slashPackage(packageArgs(evidence), {
        account: fixture.submitter.account,
      }),
      /MixedJobs/,
    );
    assert.equal(await fixture.contract.read.totalBond(), parseEther("14"));
    assert.equal(await fixture.contract.read.treasuryAccrued(), 0n);
  });

  it("rejects empty and length-mismatched package arrays without state change", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence = await makeEvidence(fixture, jobId, 0);
    await assert.rejects(
      fixture.contract.write.slashPackage(packageArgs([]), {
        account: fixture.submitter.account,
      }),
      /InvalidPackageLength/,
    );
    await assert.rejects(
      fixture.contract.write.slashPackage(
        [
          [evidence.jobId],
          [evidence.memberIndex],
          [evidence.shareHash],
          [],
          [evidence.verifierSignature],
        ],
        { account: fixture.submitter.account },
      ),
      /InvalidPackageLength/,
    );
    assert.equal(await fixture.contract.read.totalBond(), parseEther("14"));
    assert.equal(await fixture.contract.read.treasuryAccrued(), 0n);
  });

  it("rejects evidence signed for another contract domain", async function () {
    const fixture = await setup();
    const secondContract = await fixture.viem.deployContract("TraceThenSlash", [
      fixture.owner.account.address,
      fixture.verifier.account.address,
      fixture.treasury.account.address,
      CALLER_REWARD,
    ]);
    for (let index = 0; index < fixture.memberWallets.length; index += 1) {
      await secondContract.write.registerMember(
        [index, fixture.memberWallets[index].account.address],
        { account: fixture.owner.account, value: BOND },
      );
    }
    await secondContract.write.freezeCommittee({
      account: fixture.owner.account,
    });
    const secondFixture = { ...fixture, contract: secondContract };
    const { jobId } = await openJob(secondFixture);
    const wrongDomainEvidence = await makeEvidence(fixture, jobId, 0);
    await assert.rejects(
      slashOne(secondFixture, wrongDomainEvidence),
      /InvalidMemberSignature/,
    );
    assert.equal(await secondContract.read.totalBond(), parseEther("14"));
  });

  it("rejects evidence at or after release", async function () {
    const fixture = await setup();
    const { jobId, releaseTime } = await openJob(fixture, 120n);
    const evidence = await makeEvidence(fixture, jobId, 0);
    await fixture.networkHelpers.time.increaseTo(releaseTime);
    await assert.rejects(slashOne(fixture, evidence), /ReleaseWindowClosed/);
  });

  it("excludes member callers and lets the external caller withdraw the exact reward", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence = await makeEvidence(fixture, jobId, 0);
    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [
          evidence.jobId,
          evidence.memberIndex,
          evidence.shareHash,
          evidence.memberSignature,
          evidence.verifierSignature,
        ],
        { account: fixture.memberWallets[0].account },
      ),
      /MemberCallerForbidden/,
    );
    await assert.rejects(
      fixture.contract.write.slashPackage(packageArgs([evidence]), {
        account: fixture.memberWallets[6].account,
      }),
      /MemberCallerForbidden/,
    );
    await slashOne(fixture, evidence);
    const before = await fixture.publicClient.getBalance({
      address: fixture.rewardRecipient.account.address,
    });
    await fixture.contract.write.withdrawReward(
      [fixture.rewardRecipient.account.address],
      { account: fixture.submitter.account },
    );
    const after = await fixture.publicClient.getBalance({
      address: fixture.rewardRecipient.account.address,
    });
    assert.equal(after - before, CALLER_REWARD);
    assert.equal(
      await fixture.contract.read.claimableRewards([
        fixture.submitter.account.address,
      ]),
      0n,
    );
  });
});
