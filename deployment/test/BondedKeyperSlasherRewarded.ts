import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, parseEther, stringToHex } from "viem";

import {
  earlyShareTypes,
  evidenceDomain,
  type EarlyShareEvidence,
} from "../src/evidence.js";

/// Tests the parallel, additive `BondedKeyperSlasherRewarded` contract.
/// Mirrors BondedKeyperSlasher.ts's test structure exactly, adding only the
/// reward-split-specific assertions and the two new guard tests -- see
/// BondedKeyperSlasherRewarded.sol's doc-comment for why this is a separate
/// contract rather than an edit of BondedKeyperSlasher.

const BOND = parseEther("2");
const CALLER_REWARD = parseEther("0.1");

async function setup() {
  const connection = await network.create();
  const { viem, networkHelpers } = connection;
  const publicClient = await viem.getPublicClient();
  const wallets = await viem.getWalletClients();
  const [owner, verifier, ...rest] = wallets;
  const memberWallets = rest.slice(0, 7);
  const treasury = rest[7];
  const submitter = rest[8];
  const attacker = rest[9];

  const contract = await viem.deployContract("BondedKeyperSlasherRewarded", [
    owner.account.address,
    verifier.account.address,
    treasury.account.address,
    CALLER_REWARD,
  ]);

  for (let i = 0; i < memberWallets.length; i += 1) {
    await contract.write.registerMember(
      [i, memberWallets[i].account.address],
      { account: owner.account, value: BOND },
    );
  }
  await contract.write.freezeCommittee({ account: owner.account });

  return {
    contract,
    publicClient,
    networkHelpers,
    owner,
    verifier,
    treasury,
    submitter,
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
  const identityHash = keccak256(stringToHex("fc-deployment-identity"));
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

async function signatureFor(
  fixture: Awaited<ReturnType<typeof setup>>,
  evidence: EarlyShareEvidence,
  useAttacker = false,
) {
  const chainId = await fixture.publicClient.getChainId();
  const wallet = useAttacker ? fixture.attacker : fixture.verifier;
  return wallet.signTypedData({
    account: wallet.account,
    domain: evidenceDomain(chainId, fixture.contract.address, "BondedKeyperSlasherRewarded"),
    types: earlyShareTypes,
    primaryType: "EarlyShareEvidence",
    message: evidence,
  });
}

describe("BondedKeyperSlasherRewarded", function () {
  it("freezes a seven-member 4-of-7 committee with an 8-unit certificate", async function () {
    const { contract } = await setup();
    assert.equal(await contract.read.registeredCount(), 7);
    assert.equal(await contract.read.committeeFrozen(), true);
    assert.equal(await contract.read.totalBond(), 14n * 10n ** 18n);
    assert.equal(await contract.read.currentCertificate(), 8n * 10n ** 18n);
  });

  it("computes the 4-of-7 certificate from non-uniform bonds exceeding the reward", async function () {
    const connection = await network.create();
    const { viem } = connection;
    const wallets = await viem.getWalletClients();
    const [owner, verifier, treasury, ...members] = wallets;
    const contract = await viem.deployContract("BondedKeyperSlasherRewarded", [
      owner.account.address,
      verifier.account.address,
      treasury.account.address,
      10n,
    ]);
    const bonds = [700n, 100n, 500n, 200n, 600n, 300n, 400n];

    for (let index = 0; index < bonds.length; index += 1) {
      await contract.write.registerMember(
        [index, members[index].account.address],
        { account: owner.account, value: bonds[index] },
      );
    }
    await contract.write.freezeCommittee({ account: owner.account });

    assert.equal(await contract.read.totalBond(), 2800n);
    assert.equal(await contract.read.currentCertificate(), 1000n);
  });

  it("slashes a verifier-attested premature share, paying the caller reward and updating the certificate", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence: EarlyShareEvidence = {
      jobId,
      memberIndex: 0,
      shareHash: keccak256(stringToHex("valid-shutter-share-bytes")),
      memberSignatureHash: keccak256(stringToHex("native-keyper-signature")),
    };
    const signature = await signatureFor(fixture, evidence);
    const treasuryBefore = await fixture.publicClient.getBalance({
      address: fixture.treasury.account.address,
    });
    const submitterBefore = await fixture.publicClient.getBalance({
      address: fixture.submitter.account.address,
    });

    const hash = await fixture.contract.write.slashEarlyShare(
      [
        evidence.jobId,
        evidence.memberIndex,
        evidence.shareHash,
        evidence.memberSignatureHash,
        signature,
      ],
      { account: fixture.submitter.account },
    );
    const receipt = await fixture.publicClient.waitForTransactionReceipt({ hash });
    const gasCost = receipt.gasUsed * receipt.effectiveGasPrice;

    const member = await fixture.contract.read.members([0n]);
    assert.equal(member[1], 0n);
    assert.equal(member[3], true);
    assert.equal(await fixture.contract.read.currentCertificate(), 6n * 10n ** 18n);

    const treasuryAfter = await fixture.publicClient.getBalance({
      address: fixture.treasury.account.address,
    });
    assert.equal(treasuryAfter - treasuryBefore, BOND - CALLER_REWARD);

    const submitterAfter = await fixture.publicClient.getBalance({
      address: fixture.submitter.account.address,
    });
    assert.equal(submitterAfter - submitterBefore, CALLER_REWARD - gasCost);
  });

  it("rejects the slashed member claiming its own caller reward", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence: EarlyShareEvidence = {
      jobId,
      memberIndex: 0,
      shareHash: keccak256(stringToHex("self-slash-share")),
      memberSignatureHash: keccak256(stringToHex("self-slash-signature")),
    };
    const signature = await signatureFor(fixture, evidence);

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [
          evidence.jobId,
          evidence.memberIndex,
          evidence.shareHash,
          evidence.memberSignatureHash,
          signature,
        ],
        { account: fixture.memberWallets[0].account },
      ),
      /SelfSlashNotAllowed/,
    );
  });

  it("rejects a bond that does not exceed the caller reward", async function () {
    const connection = await network.create();
    const { viem } = connection;
    const wallets = await viem.getWalletClients();
    const [owner, verifier, treasury, member] = wallets;
    const contract = await viem.deployContract("BondedKeyperSlasherRewarded", [
      owner.account.address,
      verifier.account.address,
      treasury.account.address,
      CALLER_REWARD,
    ]);
    await assert.rejects(
      contract.write.registerMember([0, member.account.address], {
        account: owner.account,
        value: CALLER_REWARD,
      }),
      /InvalidBond/,
    );
  });

  it("rejects an attestation signed by the wrong verifier", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence: EarlyShareEvidence = {
      jobId,
      memberIndex: 1,
      shareHash: keccak256(stringToHex("share")),
      memberSignatureHash: keccak256(stringToHex("signature")),
    };
    const forged = await signatureFor(fixture, evidence, true);

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [jobId, 1, evidence.shareHash, evidence.memberSignatureHash, forged],
        { account: fixture.submitter.account },
      ),
      /InvalidVerifierSignature/,
    );
  });

  it("rejects evidence submitted at or after the release time", async function () {
    const fixture = await setup();
    const { jobId, releaseTime } = await openJob(fixture, 120n);
    const evidence: EarlyShareEvidence = {
      jobId,
      memberIndex: 2,
      shareHash: keccak256(stringToHex("share")),
      memberSignatureHash: keccak256(stringToHex("signature")),
    };
    const signature = await signatureFor(fixture, evidence);
    await fixture.networkHelpers.time.increaseTo(releaseTime);

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [jobId, 2, evidence.shareHash, evidence.memberSignatureHash, signature],
        { account: fixture.submitter.account },
      ),
      /ReleaseWindowClosed/,
    );
  });

  it("binds the verifier signature to every evidence field", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const { jobId: otherJobId } = await openJob(fixture);
    const evidence: EarlyShareEvidence = {
      jobId,
      memberIndex: 3,
      shareHash: keccak256(stringToHex("original-share")),
      memberSignatureHash: keccak256(stringToHex("signature")),
    };
    const signature = await signatureFor(fixture, evidence);
    const substitutedShareHash = keccak256(stringToHex("substituted-share"));
    const substitutedSignatureHash = keccak256(
      stringToHex("substituted-signature"),
    );

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [jobId, 3, substitutedShareHash, evidence.memberSignatureHash, signature],
        { account: fixture.submitter.account },
      ),
      /InvalidVerifierSignature/,
    );

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [
          jobId,
          3,
          evidence.shareHash,
          substitutedSignatureHash,
          signature,
        ],
        { account: fixture.submitter.account },
      ),
      /InvalidVerifierSignature/,
    );

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [jobId, 4, evidence.shareHash, evidence.memberSignatureHash, signature],
        { account: fixture.submitter.account },
      ),
      /InvalidVerifierSignature/,
    );

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [
          otherJobId,
          3,
          evidence.shareHash,
          evidence.memberSignatureHash,
          signature,
        ],
        { account: fixture.submitter.account },
      ),
      /InvalidVerifierSignature/,
    );
  });
});
