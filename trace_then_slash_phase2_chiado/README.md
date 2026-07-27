# TraceThenSlash Phase 2: Chiado-ready public replication

This package deploys three controlled 4-of-7 `TraceThenSlash` instances on
Chiado and executes:

1. four sequential evidence submissions;
2. one atomic four-member package; and
3. two repeated two-member packages.

Each member bond is exactly 2 Chiado native units and each accepted member
accrues a 0.1-unit external-caller reward. A complete run therefore locks
42 native units across the three contracts, plus gas. The deployment command
refuses to send transactions unless the explicit execution guard is set and a
preflight balance check succeeds.

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
PHASE2_BOND_NATIVE=2
```

Then run:

```text
npm run phase2:deploy
```

The script generates the verifier and seven member signing keys separately
for each instance, keeps all private keys out of the artifact, waits for
confirmations, withdraws the exact caller reward, and writes
`results/phase2_chiado.json`.

## Independent verification

On a second RPC endpoint:

```text
CHIADO_VERIFY_RPC_URL=<independent endpoint>
npm run phase2:verify
```

The verifier checks the chain id, deployment transaction input against the
locally compiled source artifact, bytecode hashes, every receipt and block
hash, constructor and committee state, member and verifier EIP-712
signatures, consumed evidence, slash/package/withdrawal events, realized
loss, caller reward, treasury accrual, and cross-mode equality.

Build and check the package manifest only after a completed run:

```text
npm run manifest:build
npm run manifest:check
```
