import { network } from "hardhat";
import { formatEther } from "viem";

const connection = await network.connect();
const { viem } = connection;
const wallets = await viem.getWalletClients();
const client = await viem.getPublicClient();
const owner = wallets[0];

if (owner?.account === undefined) {
  throw new Error("Deployer account unavailable.");
}

const chainId = await client.getChainId();
const address = owner.account.address;
const balance = await client.getBalance({ address });
const minimum = 62_000_000_000_000_000n;

console.log(`chainId=${chainId}`);
console.log(`deployer=${address}`);
console.log(`balanceWei=${balance}`);
console.log(`balanceXDAI=${formatEther(balance)}`);
console.log(`minimumWei=${minimum}`);
console.log(`balance_ok=${balance >= minimum}`);

if (chainId !== 10200) {
  throw new Error(`Expected Chiado 10200, received ${chainId}.`);
}
