import hardhatToolboxViemPlugin from "@nomicfoundation/hardhat-toolbox-viem";
import { configVariable, defineConfig } from "hardhat/config";
import { fileURLToPath } from "node:url";

const solcPath = fileURLToPath(
  new URL("./node_modules/solc/soljson.js", import.meta.url),
);

export default defineConfig({
  plugins: [hardhatToolboxViemPlugin],
  solidity: {
    profiles: {
      default: {
        version: "0.8.28",
        path: solcPath,
        settings: {
          optimizer: { enabled: true, runs: 200 },
          evmVersion: "cancun",
        },
      },
      production: {
        version: "0.8.28",
        path: solcPath,
        settings: {
          optimizer: { enabled: true, runs: 200 },
          evmVersion: "cancun",
        },
      },
    },
  },
  networks: {
    hardhatMainnet: {
      type: "edr-simulated",
      chainType: "l1",
      hardfork: "cancun",
    },
    chiado: {
      type: "http",
      chainType: "l1",
      chainId: 10200,
      url: configVariable("CHIADO_RPC_URL"),
      accounts: [configVariable("CHIADO_DEPLOYER_PRIVATE_KEY")],
    },
  },
});
