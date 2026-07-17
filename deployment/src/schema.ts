import type { Address, Hex } from "viem";

export type KeyperEntry = { index: number; address: Address };

export type KeyperSetFile = {
  schema: "threshcert-keyper-set-v1";
  rollingShutterVersion?: string;
  rollingShutterCommit?: string;
  threshold: number;
  keypers: KeyperEntry[];
};

export type TransactionRecord = {
  hash: Hex;
  blockNumber: string;
  blockHash: Hex;
  gasUsed: string;
  effectiveGasPrice: string;
  status: string;
};

export type DeploymentFile = {
  schema: "threshcert-bonded-keyper-deployment-v1";
  generatedAt: string;
  networkName: string;
  chainId: number;
  contract: Address;
  owner: Address;
  verifier: Address;
  treasury: Address;
  committeeSize: 7;
  threshold: 4;
  bondWeiPerMember: string;
  totalBondWei: string;
  initialCertificateWei: string;
  keypers: KeyperEntry[];
  transactions: {
    deploy: TransactionRecord;
    registrations: Array<TransactionRecord & { memberIndex: number }>;
    freeze: TransactionRecord;
  };
};

export type JobFile = {
  schema: "threshcert-release-job-v1";
  generatedAt: string;
  deploymentFile: string;
  chainId: number;
  contract: Address;
  jobId: Hex;
  eon: string;
  identityPreimage: Hex;
  identityHash: Hex;
  releaseTime: string;
  nonce: string;
  transaction: TransactionRecord;
};

export type ExportedShare = {
  memberIndex: number;
  keyperAddress: Address;
  share: Hex;
  shareHash?: Hex;
  publicKeyShare?: Hex;
  shareValid: boolean;
  nativeSignature: Hex;
  nativeSignatureHash?: Hex;
  nativeSignatureValid: boolean;
};

export type EvidenceFile = {
  schema: "threshcert-shutter-evidence-v1";
  generatedAt: string;
  rollingShutterVersion: string;
  rollingShutterCommit: string;
  instanceId: number;
  eon: string;
  epochId: string;
  threshold: number;
  numKeypers: number;
  identityPreimage: Hex;
  identityHash: Hex;
  aggregateKey: Hex;
  aggregateKeyValid: boolean;
  reconstructionMatchesStoredKey: boolean;
  shares: ExportedShare[];
};
