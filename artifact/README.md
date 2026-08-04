# Reproducibility artifact v49

This archive separates the v49 manuscript checks from retained exploratory and
legacy modules. It also separates integrity verification from fresh tool
execution. A preserved Halmos certificate is not described as a rerun.

The payment claim is the named acquirer's net irreversible outflow in the typed
asset, unit, control closure, funding lookback, and refund horizon. Legacy
member-loss sentinels and the unbridged values 4, 18, and 40 are not
attacker-payment certificates.

The checker takes an explicitly materialized finite acquisition LTS. It does not
derive routes from bytecode, crawl deployments, or prove route completeness.
Any deployment-wide lift requires an independent coverage/refinement proof.
TRUST_AND_CHECKING_BOUNDARY.md separates fresh machine checks, preserved-proof
integrity, human semantic lemmas, and external cryptographic/economic assumptions.

## Integrity and preserved-proof verification

Prerequisites: Node.js 20+ and Python 3.10+. From the extracted archive root:

```text
node verify_integrity_v49.mjs
```

This offline entry point checks the root manifest and frozen Git object,
verifies the raw HTML/JSON/RPC recapture, regenerates the finite-LTS evidence
result, byte-compares generated and canonical JSON, reruns the admission/refresh
formula checks, and checks the preserved Hardhat and Halmos certificates
against their bound sources, transcripts, proof names, empty bounds, and
runtime hashes. The finite-LTS stage runs 40 malformed-schema regressions,
eight raw-JSON rejection cases, four semantic counterexamples, four
exact-rational tests, three exact-boundary cases, and 1,024 fixed-graph
monotonicity comparisons. It prints
`FORMAL_MODE=PRESERVED_PROOF_HASH_AND_SEMANTIC_VERIFICATION_NOT_REEXECUTION` and
does not invoke Halmos. The final v49 run took about 30 seconds on the reference host; filesystem and antivirus overhead vary.

`node verify_paper_v49.mjs` is a thin compatibility alias for this integrity
entry point.

## Fresh source rebuild and proof re-execution

```text
node verify_rebuild_v49.mjs
```

This entry point installs locked Node dependencies when absent, force-recompiles
the Solidity sources with solc 0.8.28/Cancun, requires all 11 Hardhat tests, and
freshly invokes Halmos 0.3.3 with Yices 2.6.4, loop bound eight, and four jobs.
It writes proof outputs only to a validated system-temporary directory, then
compares all 82 proof names, zero failures, empty bounds, source/config hashes,
and compiled runtime with the canonical certificate before removing the temp
directory. It prints `V49_FRESH_REBUILD=PASS` only after this re-execution. The final v49 run, including creation of the locked Python environment, took 1,266 seconds (21 minutes 6 seconds) on the reference host; solver, network-cache, and CPU variability can change that time substantially.

Foundry must be on `PATH` or named by `FOUNDRY_BIN`. The driver creates an
excluded local Python virtual environment when needed; `V49_PYTHON` may instead
name an existing Python that provides Halmos 0.3.3. On Windows/Python 3.11 the
portable environment uses `eth-hash[pycryptodome]` because the obsolete
`safe-pysha3` source dependency requires a separate MSVC toolchain. The
preserved filename `requirements-v48-portable.txt` dates that dependency lock,
not the v49 checker or manuscript.
## Full archival verification

```text
node verify_all.mjs
```

The final v49 archival driver took 168 seconds on the reference host. It additionally runs preserved Chiado evidence, the withdrawn
third-party contract survey, financing/activation formula families, and other
historical checks. It labels those sections `EXPLORATORY_NOT_USED_BY_V49` or
`ARCHIVAL_FORMULA_FAMILIES_NOT_USED_BY_V49`. They are retained for provenance,
not used as evidence for the v49 manuscript.
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
- `production_snapshot/`: fixed Gnosis block and set-10 snapshot record,
  member evidence ledger, canonical result, offline recomputation, and read-only RPC check.
- `core_formula_checks/`: independent enumerations for sequential closure,
  information boundaries, partial activation evidence, atomic-bypass and mixed
  evidence certificates, common-solvency settlement separation, and finite
  countermodels for the two RPSC mechanism-lifting premises.
- `joint_incidence_refinement/`: finite-schema checkers, Solidity/Hardhat
  fixtures (including the prefunded threshold exchange), deployment
  capture/admission and tamper checkers, Foundry/Halmos harness, preserved
  certificates/log, locked build metadata, and tests.
- `threshold_deployment_audit/`: frozen four-case cohort, pinned structured
  capture, per-case v2 evidence records under the v3 checker policy, 36 raw
  public responses plus two indexes, strict supplied-LTS status checker,
  canonical generated decisions, and offline byte-comparison verifiers. Two finite-state fixtures are separately labelled
  as constructed diagnostics.
- `third_party_contract_survey/`: preserved exploratory stress cohort. The v49
  paper does not use it for a prevalence or contribution claim.
- `chiado_public_runs/`: TraceThenSlash source, build metadata, deployment and
  read-only verification scripts, plus both canonical result JSON files.

The separate joint-incidence finite-schema check establishes its 117-state by
exactly-35-terminal product, terminal-family completeness, payment-labelled
closed-contract trace--outcome correspondence, and exact
acquisition-call-value arithmetic. The formal tier additionally establishes the
restricted fixture-specific EVM-to-schema bridge and, inside the admitted
contract ledger, controller-funded credits, external exact-value acquisition
funding with no payer refund/withdrawal path, and transfer of four controlled
share rights. It does not establish off-contract reimbursement closure, distinct
beneficial ownership, cryptographic usability of the rights, member willingness,
or production pass-through. The Chiado runs validate controlled contract
behavior only.