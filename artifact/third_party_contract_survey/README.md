# Third-party closed-contract admission survey

This directory is deliberately separate from the frozen paper artifact. It
extracts only the reusable layers of the constructed-contract admission check.
The original verifier is not contract-generic: it hard-codes the
OverlappingPoolEscrow constructor, seven members, three controller immutable
references, initial getters, mutating ABI, and one guarded `CALL`.

The survey therefore separates five layers:

1. pinned-chain and runtime-hash provenance;
2. direct-creation and creation-bytecode identity;
3. runtime-template equality modulo compiler-declared immutable/library ranges;
4. ABI and executable-opcode inventory, including proxy slots;
5. contract-specific economic-incidence evidence.

Layers 1--4 are reusable. Layer 5 is never inferred from bytecode shape. A
contract without machine-checkable entry closure, payer separation, payment
preservation, backward realization, terminal equivalence, and offset closure
is `FAIL_CLOSED`, not "insecure". This distinction makes negative survey
results interpretable instead of rejecting every third-party contract merely
because it has a different schema.

Capture a pinned runtime record:

```text
node capture_runtime.mjs --rpc RPC_URL --address 0xADDRESS --block NUMBER --out records/name.json
```

If the direct deployment transaction is known, add
`--deployment-tx 0xHASH`. Screen it with a compiler artifact when one is
available:

```text
node screen_contract.mjs --record records/name.json --artifact artifacts/name.json --policy policy.direct-closed-contract.v1.json --out results/name.json
```

Without an artifact, template/ABI checks remain `NOT_EVALUATED`; without a
contract-specific semantic certificate, the final result remains
`FAIL_CLOSED`. Survey inclusion criteria, addresses, pinned blocks, sources,
and every input/output SHA-256 must be fixed before aggregate claims are made.

The frozen initial cohort and its common block are recorded in
`cohort.ethereum-mainnet.v1.json`. Results use a three-way reusable-layer
status: `PASS`, `FAIL`, or `INCOMPLETE`. Full incidence admission remains
separate and fail-closed. See `SURVEY_REPORT.md` and reproduce the frozen
aggregate with:

```text
node test_screen_contract_v2.mjs
node aggregate_results_v2.mjs
node verify_manifest_v2.mjs
```
