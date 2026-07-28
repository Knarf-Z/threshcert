# Verification record

Recorded on 2026-07-26 with Node.js 24.14.0, Hardhat 3.9.1, Solidity
0.8.28, and the Cancun EVM target. The Solidity compiler used the optimized
IR pipeline with 200 optimizer runs.

## Compilation and adversarial tests

`npm run typecheck && npm test` compiled the contract, passed strict
TypeScript checking, and returned 10/10 passing tests:

1. positive frozen 4-of-7 threshold-bond floor;
2. four sequential submissions;
3. one atomic four-member package;
4. two repeated two-member packages;
5. maximum seven-member package without an external \(b\);
6. whole-package rollback on one forged verifier signature;
7. rejection of a wrong member signature;
8. rejection of duplicate members in a package;
9. rejection at or after release; and
10. exact caller-reward withdrawal.

## Independently recomputed result

`npm run scenarios && npm run verify:results` executed fresh local-EVM
deployments for the three positive scenarios and then recomputed their
invariants from the JSON record:

```text
PHASE1_CERTIFICATE=POSITIVE_SCOPED
LOWER_BOUND_WEI=8000000000000000000
SEQUENTIAL_ATOMIC_REPEATED_EQUIVALENCE=PASS
CALLER_REWARD_ACCRUAL=PASS
NO_EXTERNAL_PACKAGE_BOUND_B=PASS
SCOPE_GUARDS=PASS
MANIFEST=PASS
```

The transaction hashes and gas use are preserved in
`results/phase1_scenarios.json`. They identify executions on fresh ephemeral
Hardhat chains (chain ID 31337), not public-network transactions.
