# TraceThenSlash Phase 2: Chiado-ready public replication

This package deploys three controlled 4-of-7 `TraceThenSlash` instances on
Chiado and executes:

1. four sequential evidence submissions;
2. one atomic four-member package; and
3. two repeated two-member packages.

The low-budget default uses a 0.002-Chiado-xDAI bond per member and a
0.0005-xDAI external-caller reward per covered slash. The reward is deliberately
configurable: the public result is accepted only if its four rewards cover the
observed gas cost of the slash transaction(s) and reward withdrawal in every
mode. A complete three-instance run commits 0.042 xDAI of principal and
reserves 0.02 xDAI for gas. The deployment command refuses to send
transactions unless the explicit execution guard is set, a preflight balance
check succeeds, and total principal stays below the configured 0.1-xDAI safety
cap.

The result is a public, controlled enforcement-loss experiment. It does not
claim seven independent operators, production economics, silent-leakage
coverage, or an unconditional attacker-payment lower bound.

## Local readiness check

```text
npm ci
npm run ready
```

This compiles the exact contract and runs the Phase 1 adversarial test suite
without sending public transactions.

## Public execution

Supply the RPC and funded deployer through environment variables or the
Hardhat keystore:

```text
CHIADO_RPC_URL
CHIADO_DEPLOYER_PRIVATE_KEY
PHASE2_EXECUTE=I_UNDERSTAND_PUBLIC_TRANSACTIONS
PHASE2_BOND_NATIVE=0.002
PHASE2_CALLER_REWARD_NATIVE=0.0005
PHASE2_GAS_RESERVE_NATIVE=0.02
PHASE2_MAX_TOTAL_NATIVE=0.1
```

Then run:

```text
npm run phase2:deploy
```

The bond denomination can be changed, but this does not change the
package-invariance claim: each mode must realize exactly four bonds of loss.
Increasing it above the default requires raising the explicit total-principal
cap as a separate confirmation.

The script generates the verifier and seven member signing keys separately
for each instance, keeps all private keys out of the artifact, uses the funded
deployer as the recoverable treasury, waits for confirmations, withdraws the
exact caller reward and treasury accrual, and writes
`results/phase2_chiado.json`. It records each receipt's effective gas price and
gas cost. If any mode's reward fails to cover the independently recomputable
enforcement gas cost, the result is marked underfunded and the command fails.

## Independent verification

On the official archive endpoint, distinct from the deployment endpoint:

```text
CHIADO_VERIFY_RPC_URL=https://rpc.chiado.gnosis.gateway.fm
npm run phase2:verify
```

The verifier does not fall back to `CHIADO_RPC_URL`. It checks the chain id,
deployment sender, target and contract address, deployment transaction input
against the locally compiled source artifact, bytecode hashes, every receipt
and block hash, historical terminal state, member and verifier EIP-712
signatures, consumed evidence, slash/package/withdrawal event amounts,
realized covered-bond loss, exact caller and treasury withdrawals, observed
gas coverage, and cross-mode equality.

## Recovering the remaining bonds

The six unslashed owner-funded bonds across the preserved calibration and
covered runs remain locked through their release windows. The settlement
script reads both `phase2_chiado_underfunded_run1.json` and
`phase2_chiado_covered_run2.json`, rejects duplicate addresses, and recovers
exactly 0.108 xDAI across all six contracts. The latest recorded release time
is 2026-08-04 01:47:30 UTC (2026-08-04 09:47:30 UTC+08:00); run only after
that time:

```text
PHASE2_SETTLE=I_UNDERSTAND_PUBLIC_SETTLEMENT
npm run phase2:settle
```

Settlement is irreversible, prevents future release jobs, and incrementally
writes `results/phase2_settlement.json`. A rerun audits already retired
contracts from `RemainingBondsWithdrawn` events, so interruption does not hide
a partial recovery. Final PASS requires six records and 108000000000000000
wei. The independent verifier reads the historical
terminal block recorded by the deployment run, so later settlement does not
invalidate the original public certificate.

Build and check the package manifest only after a completed run:

```text
npm run manifest:build
npm run manifest:check
```
