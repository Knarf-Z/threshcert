# Reproducibility artifact v47

This archive separates the v47 manuscript checks from retained exploratory and
legacy modules. The legacy sentinel `0_PUBLIC_FLOOR_CERTIFICATE` belongs to the
member-loss submodule; it is **not** the deployment-wide attacker-payment
certificate. The bridge audit uses `ATTACKER_PAYMENT_NOT_CERTIFIED` when public
evidence leaves a positive route unsupported.

The archive keeps locked dependencies, contract source and build metadata,
canonical JSON results, the pinned four-system capture, and an offline Git
bundle containing the frozen-plan commit. It performs no network access or
chain write during verification.

## Paper-only one-command verification

Prerequisites: Node.js 20+ and Python 3.10+. From the extracted archive root:

```text
node verify_paper_v47.mjs
```

This is the default manuscript reproduction path. It verifies the root
manifest, recomputes the frozen Git commit object hash, checks the four-system
bridge audit and pinned Shutter snapshot, runs the member-loss and refresh
experiments, checks the prefunded payment-accounting core and its admitted EVM
refinement, and reproduces the `0/4/18/40` quantitative table. It checks the
manifest again before returning `PAPER_V47_CLAIMS=PASS` and prints its measured
runtime. The reference run took approximately 19 seconds. The four displayed
values are deliberately typed as `CERTIFIED_ATTACKER_PAYMENT=0`,
`UNBRIDGED_MEMBER_FLOOR_PROXY=4`, `UNBRIDGED_LOWER_TAIL_PROXY=18`, and
`INVALID_MEAN_HEURISTIC=40`: only the first is an attacker-payment certificate.

## Full archival verification

```text
node verify_all.mjs
```

The archival driver took approximately two minutes (121.6 seconds) on the
reference host. It additionally runs preserved Chiado evidence, the withdrawn
third-party contract survey, financing/activation formula families, and other
historical checks. It labels those sections `EXPLORATORY_NOT_USED_BY_V47` or
`ARCHIVAL_FORMULA_FAMILIES_NOT_USED_BY_V47`. They are retained for provenance,
not used as evidence for the v47 manuscript.
The joint-incidence certificate reports `CONFIGURATION_PREFIX_TOTALITY=PASS`
and `POSTCONFIGURATION_EVM_TO_SCHEMA_BRIDGE=PASS` only for an admitted Cancun
runtime and the declared universe. Admission checks the direct creation input,
constructor, runtime template modulo immutables, fresh state, ABI, and opcode
closure; ten tampered records are rejected. A symbolic configuration proof
constructs every admissible root; the refined LTS then covers `acquireFour` and
`withdraw`. On all 35 acquisition terminals, credits, every wrong `uint256`
payment, and a permitted payer address are symbolic; payer/acquirer ownership
and zero payer-claimable balance are asserted. Eight role-conflict obligations
cover the excluded caller roles. Two concrete hostile-member obligations check
the complete mutating-reentry basis; arbitrary-callee closure remains the stated
EVM call/storage-isolation argument, not quantification over unknown bytecode. The
machine-readable obligation map states the evidence for every refinement clause,
terminal-family completeness, closed-contract trace--outcome correspondence,
economic incidence, and the trusted computing base. The preserved
Halmos/Yices run has 82 proofs, zero failures, and empty bounds. This is not a
result about arbitrary contracts or production Shutter. See
`SEMANTIC_SCOPE.md` for the external cryptographic and beneficial-control lift.

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

- `evidence_admission/`: report-invariant collateral-floor admission, refresh-window paired-world and duration experiments, canonical JSON, expected console output, and focused unit tests.
- `production_snapshot/`: fixed Gnosis block and active-set record, member
  evidence ledger, canonical result, offline recomputation, and read-only RPC check.
- `core_formula_checks/`: independent enumerations for sequential closure,
  information boundaries, partial activation evidence, atomic-bypass and mixed
  evidence certificates, common-solvency settlement separation, and finite
  countermodels for the two RPSC mechanism-lifting premises.
- `joint_incidence_refinement/`: finite-schema checkers, Solidity/Hardhat
  fixtures (including the prefunded threshold exchange), deployment
  capture/admission and tamper checkers, Foundry/Halmos harness, preserved
  certificates/log, locked build metadata, and tests.
- `threshold_deployment_audit/`: prospectively frozen author-controlled cohort and policy, pinned public
  capture for Gnosis Shutter, SSV, tBTC v2, and drand, per-gate rejection
  reasons, canonical result, and an offline verifier.
- `third_party_contract_survey/`: preserved exploratory stress cohort. The v47
  paper does not use it for a prevalence or contribution claim.
- `chiado_public_runs/`: TraceThenSlash source, build metadata, deployment and
  read-only verification scripts, plus both canonical result JSON files.

The finite check establishes its 117-state by exactly-35-terminal product,
terminal-family completeness, payment-labelled closed-contract trace--outcome
correspondence, and exact acquisition-call-value arithmetic. The formal tier additionally establishes the
restricted fixture-specific EVM-to-schema bridge and, inside the admitted
contract ledger, controller-funded credits, external exact-value acquisition
funding with no payer refund/withdrawal path, and transfer of four controlled
share rights. It does not establish off-contract reimbursement closure, distinct
beneficial ownership, cryptographic usability of the rights, member willingness,
or production pass-through. The Chiado runs validate controlled contract
behavior only.