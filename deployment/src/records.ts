import type { TransactionReceipt } from "viem";

import type { TransactionRecord } from "./schema.js";

export function transactionRecord(receipt: TransactionReceipt): TransactionRecord {
  return {
    hash: receipt.transactionHash,
    blockNumber: receipt.blockNumber.toString(),
    blockHash: receipt.blockHash,
    gasUsed: receipt.gasUsed.toString(),
    effectiveGasPrice: receipt.effectiveGasPrice.toString(),
    status: receipt.status,
  };
}
