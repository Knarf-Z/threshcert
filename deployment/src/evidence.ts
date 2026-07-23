import type { Address, Hex, WalletClient } from "viem";

export const earlyShareTypes = {
  EarlyShareEvidence: [
    { name: "jobId", type: "bytes32" },
    { name: "memberIndex", type: "uint8" },
    { name: "shareHash", type: "bytes32" },
    { name: "memberSignatureHash", type: "bytes32" },
  ],
} as const;

export type EarlyShareEvidence = {
  jobId: Hex;
  memberIndex: number;
  shareHash: Hex;
  memberSignatureHash: Hex;
};

export function evidenceDomain(
  chainId: number,
  verifyingContract: Address,
  name: string = "BondedKeyperSlasher",
) {
  return {
    name,
    version: "1",
    chainId,
    verifyingContract,
  } as const;
}

export async function signEvidence(
  wallet: WalletClient,
  chainId: number,
  verifyingContract: Address,
  evidence: EarlyShareEvidence,
): Promise<Hex> {
  if (wallet.account === undefined) {
    throw new Error("wallet client has no signing account");
  }
  return wallet.signTypedData({
    account: wallet.account,
    domain: evidenceDomain(chainId, verifyingContract),
    types: earlyShareTypes,
    primaryType: "EarlyShareEvidence",
    message: evidence,
  });
}

