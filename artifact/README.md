# Anonymous reproducibility artifact

This is the complete review artifact for the anonymized manuscript. It keeps
locked dependencies, contract source and build metadata, canonical result
JSON, the failed calibration JSON, the fresh covered-run JSON, and executable
checkers in one tree. It also includes the pinned Gnosis production snapshot,
its public-evidence ledger and canonical zero-certificate result, plus offline and
read-only archive-RPC verification. Raw terminal transcripts are omitted because
they contain local paths; no canonical result JSON is omitted.

## One-command offline verification

Prerequisites: Node.js 20+ and Python 3.10+. From the extracted archive root:

```text
node verify_all.mjs
```

The command verifies the root manifest, recomputes the pinned Gnosis production
snapshot certificate, checks both preserved Chiado result files, their full
identifiers and six-contract 0.108-xDAI settlement plan, checks the declared
finite transaction schema with independent Node and Python implementations,
and runs the core formula checks. It performs no network access or chain write.

The schema certificate deliberately reports
`EVM_TO_SCHEMA_BRIDGE=NOT_PROVED`. Source, ABI, build, bytecode, and opcode
checks are preserved as implementation audit evidence; they are not described
as a proof covering every EVM execution.

## Independent archive-RPC verification

The pinned production snapshot can be rechecked against a user-supplied,
read-only Gnosis archive endpoint:

```text
python production_snapshot/scripts/verify_production_snapshot_live.py --rpc <archive-rpc-url>
```

The preserved public-chain JSON can additionally be checked against Chiado by
supplying a read-only archive endpoint distinct from the deployment endpoint:

```text
cd chiado_public_runs
npm ci --no-audit --no-fund
CHIADO_VERIFY_RPC_URL=<archive-rpc-url> npm run phase2:verify
```

On PowerShell, set `$env:CHIADO_VERIFY_RPC_URL` first and then run
`npm run phase2:verify`. The verifier recompiles the pinned source and checks
chain ID, deployment inputs, bytecode, receipts, block hashes, signatures,
events, historical state, exact reward/treasury accounting, cross-mode
equality, and the recorded coverage condition.

## Contents and claim boundary

- `production_snapshot/`: fixed Gnosis block and active-set record, member
  evidence ledger, canonical result, offline recomputation, and read-only RPC check.
- `core_formula_checks/`: independent enumerations for the sequential closure,
  information boundary, atomic-bypass hierarchy, and common-solvency
  settlement separation.
- `joint_incidence_refinement/`: the normative finite-schema checkers,
  Solidity fixture, locked build metadata, and behavioral tests.
- `chiado_public_runs/`: TraceThenSlash source, build metadata, deployment and
  read-only verification scripts, plus both canonical result JSON files.

The finite schema check establishes its 117-state by 35-terminal product and
exact residual-payment arithmetic. It does not establish the EVM-to-schema
semantic bridge, beneficial-owner independence, member willingness, production
pass-through, or real attacker payment. The Chiado runs validate controlled
contract behavior only.