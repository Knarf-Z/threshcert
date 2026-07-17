import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { network } from "hardhat";
import { keccak256, parseEther, stringToHex } from "viem";

import {
  earlyShareTypes,
  evidenceDomain,
  type EarlyShareEvidence,
} from "../src/evidence.js";

const BOND = parseEther("2");

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

  const contract = await viem.deployContract("BondedKeyperSlasher", [
    owner.account.address,
    verifier.account.address,
    treasury.account.address,
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
  };
}

async function openJob(
  fixture: Awaited<ReturnType<typeof setup>>,
  secondsFromNow = 3_600n,
) {
  const latest = await fixture.publicClient.getBlock();
  const releaseTime = latest.timestamp + secondsFromNow;
  const eon = 1n;
  const identityHash = keccak256(stringToHex("threshcert-deployment-identity"));
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
    domain: evidenceDomain(chainId, fixture.contract.address),
    types: earlyShareTypes,
    primaryType: "EarlyShareEvidence",
    message: evidence,
  });
}

describe("BondedKeyperSlasher", function () {
  it("rejects registering one signer in two committee positions", async function () {
    const connection = await network.create();
    const { viem } = connection;
    const wallets = await viem.getWalletClients();
    const [owner, verifier, treasury, member] = wallets;
    const contract = await viem.deployContract("BondedKeyperSlasher", [
      owner.account.address,
      verifier.account.address,
      treasury.account.address,
    ]);
    await contract.write.registerMember([0, member.account.address], {
      account: owner.account,
      value: BOND,
    });
    await assert.rejects(
      contract.write.registerMember([1, member.account.address], {
        account: owner.account,
        value: BOND,
      }),
      /DuplicateSigner/,
    );
  });

  it("freezes a seven-member 4-of-7 committee with an 8-unit certificate", async function () {
    const { contract } = await setup();
    assert.equal(await contract.read.registeredCount(), 7);
    assert.equal(await contract.read.committeeFrozen(), true);
    assert.equal(await contract.read.totalBond(), 14n * 10n ** 18n);
    assert.equal(await contract.read.currentCertificate(), 8n * 10n ** 18n);
  });

  it("slashes a verifier-attested premature share and updates the certificate", async function () {
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

    await fixture.contract.write.slashEarlyShare(
      [
        evidence.jobId,
        evidence.memberIndex,
        evidence.shareHash,
        evidence.memberSignatureHash,
        signature,
      ],
      { account: fixture.submitter.account },
    );

    const member = await fixture.contract.read.members([0n]);
    assert.equal(member[1], 0n);
    assert.equal(member[3], true);
    assert.equal(await fixture.contract.read.currentCertificate(), 6n * 10n ** 18n);
    const treasuryAfter = await fixture.publicClient.getBalance({
      address: fixture.treasury.account.address,
    });
    assert.equal(treasuryAfter - treasuryBefore, BOND);
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

  it("binds the verifier signature to the exact share hash", async function () {
    const fixture = await setup();
    const { jobId } = await openJob(fixture);
    const evidence: EarlyShareEvidence = {
      jobId,
      memberIndex: 3,
      shareHash: keccak256(stringToHex("original-share")),
      memberSignatureHash: keccak256(stringToHex("signature")),
    };
    const signature = await signatureFor(fixture, evidence);
    const substitutedShareHash = keccak256(stringToHex("substituted-share"));

    await assert.rejects(
      fixture.contract.write.slashEarlyShare(
        [jobId, 3, substitutedShareHash, evidence.memberSignatureHash, signature],
        { account: fixture.submitter.account },
      ),
      /InvalidVerifierSignature/,
    );
  });
});
