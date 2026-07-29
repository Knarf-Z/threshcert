import { keccak256, type Address, type Hex, type WalletClient } from "viem";

export const earlyShareArtifactTypes = {
  EarlyShareArtifact: [
    { name: "jobId", type: "bytes32" },
    { name: "memberIndex", type: "uint8" },
    { name: "shareHash", type: "bytes32" },
  ],
} as const;

export const earlyShareEvidenceTypes = {
  EarlyShareEvidence: [
    { name: "jobId", type: "bytes32" },
    { name: "memberIndex", type: "uint8" },
    { name: "shareHash", type: "bytes32" },
    { name: "memberSignatureHash", type: "bytes32" },
  ],
} as const;

export type EarlyShareArtifact = {
  jobId: Hex;
  memberIndex: number;
  shareHash: Hex;
};

export function traceThenSlashDomain(
  chainId: number,
  verifyingContract: Address,
) {
  return {
    name: "TraceThenSlash",
    version: "1",
    chainId,
    verifyingContract,
  } as const;
}

export async function signArtifact(
  wallet: WalletClient,
  chainId: number,
  verifyingContract: Address,
  artifact: EarlyShareArtifact,
): Promise<Hex> {
  if (wallet.account === undefined) {
    throw new Error("member wallet has no signing account");
  }
  return wallet.signTypedData({
    account: wallet.account,
    domain: traceThenSlashDomain(chainId, verifyingContract),
    types: earlyShareArtifactTypes,
    primaryType: "EarlyShareArtifact",
    message: artifact,
  });
}

export async function signVerifierEvidence(
  wallet: WalletClient,
  chainId: number,
  verifyingContract: Address,
  artifact: EarlyShareArtifact,
  memberSignature: Hex,
): Promise<Hex> {
  if (wallet.account === undefined) {
    throw new Error("verifier wallet has no signing account");
  }
  return wallet.signTypedData({
    account: wallet.account,
    domain: traceThenSlashDomain(chainId, verifyingContract),
    types: earlyShareEvidenceTypes,
    primaryType: "EarlyShareEvidence",
    message: {
      ...artifact,
      memberSignatureHash: keccak256(memberSignature),
    },
  });
}
