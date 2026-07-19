# ThreshCert complete experiment bundle

ThreshCert is a reproducible artifact for threshold attack-cost certificates,
activation-aware evidence acquisition, coordinated defense, and
evidence-gated slashing. This complete bundle contains a pinned production
deployment evidence audit, all original certificate, activation, allocation,
exact-solver, defense-lattice, Möbius, penalty-evidence, Dune/GPv2, and public
Chiado pilot materials. The three added
scalability, parameter-sensitivity, and baseline-comparison studies remain
isolated in `extended_experiments/`, so reproducing them does not overwrite the
original experiment results.

Authors: Jiaqi Zhang
([ORCID 0009-0005-3271-3106](https://orcid.org/0009-0005-3271-3106)) and
Honghao Fu
([ORCID 0000-0002-1934-3391](https://orcid.org/0000-0002-1934-3391)).
See `CITATION.cff` for machine-readable citation metadata and `EXPERIMENTS.md`
for the complete inventory and claim boundaries.

It intentionally excludes virtual environments, IDE metadata, `.env` files,
and secrets.

`RESULTS_SUMMARY.md` gives the compact reproduced findings. `EXPERIMENTS.md`
defines every experiment and its interpretation boundary.

## Contents

- `data/shutter_keyper_snapshot.json`: the production committee snapshot pinned
  to Gnosis block `46,666,718` and its block hash.
- `data/production_keyper_set_20260613.json`: the manager, set contract,
  creation and registration transactions, activation block, four-of-seven
  threshold, and seven real member addresses retrieved at the pinned block.
- `data/production_member_evidence.csv`: the seven-row evidence audit covering
  resistance, activation, attribution, forfeiture, joint enforcement
  probability, and insurance or compensation for every production member.
- `scripts/run_production_evidence_audit.py`: validates all cross-record
  bindings, applies the evidence gates, computes the production lower bound,
  and writes the per-member audit and evidence-gap result files.
- `scripts/verify_production_snapshot_live.py`: optional standard-library live
  recheck of the fixed block, contracts, event, threshold, and seven members.
- `data/gnosis_counterfactual_fixture.json`: a separate counterfactual ledger
  with explicitly hypothetical resistance and activation floors, denominated
  only in normalized cost units, on the pinned seven-member, four-of-seven
  committee geometry.
- `scripts/run_gnosis_counterfactual.py`: sends that fixture through the exact
  subset-state solver and the certificate gates, including all 21 seed-member
  placements.
- `results/gnosis_counterfactual_result.json`: records public `0`, TC `4`, AC
  `10`, gate-rejected fallback `4`, and both witnesses with the non-production
  claim boundary.
- `tests/test_gnosis_counterfactual.py`: verifies the geometry binding,
  witnesses, seed-position invariance, gate fallback, and portable JSON bytes.
- `paper/section7_evaluation.tex`: paper update centered on the production
  audit and strictly conditioned counterfactual, with related evidence panels
  arranged as paired `subtable`s.
- `paper/conclusion_counterfactual_sentence.tex`: synchronized conclusion
  sentence that keeps the actual production certificate at zero.
- `paper/abstract_evaluation_sentence.txt`: compact abstract replacement that
  distinguishes controlled branch checks from the production evidence audit.
- `data/evidence_ledger_public_only.csv`: address-level compatibility view of
  the production audit for the basic threshold-cover verifier.
- `data/evidence_ledger_controlled_positive.csv`: a controlled positive ledger used only to test the verifier. It is not deployment evidence.
- `scripts/verify_certificate.py`: computes the uniform threshold-cover certificate.
- `scripts/run_controlled_checks.py`: writes the activation-ladder, mechanism-scope, defensive-allocation, and sensitivity outputs.
- `scripts/run_scaling_benchmark.py`: runs a machine-specific exact subset-state scaling check.
- `extended_experiments/`: self-contained scalability,
  certificate-computation cost, parameter-sensitivity, and baseline-comparison
  experiments with their own inputs, results, tests, and reproduction command.
- `scripts/defense_lattice.py`: exact sequential solver, Boolean-lattice
  transforms, target-plan enumeration, and allocation utilities.
- `scripts/run_lattice_mobius_experiments.py`: writes the pure high-order,
  low-order truncation, random four-of-seven, target-lattice, and greedy-decoy
  results.
- `tests/test_defense_lattice.py`: standard-library unit tests for the new
  lattice and Möbius calculations.
- `results/solver_scaling_repeats/`: all ten raw benchmark repeats from the
  recorded Windows/Python 3.11.1 machine.
- `deployment/`: Solidity, Hardhat, Rolling Shutter 7-process overlay, the Go
  BLS/native-signature evidence exporter, and the Chiado transaction scripts.
- `deployment/certificates/chiado-execution-certificate.json`: a
  machine-readable positive certificate for the recorded controlled Chiado
  mechanism. It binds the exact lower-tail calculation to hashed evidence
  records and explicitly marks production Shutter resistance as not certified.
- `deployment/scripts/verify_chiado_certificate.py`: deterministic offline
  verification of that certificate and all source-file bindings.

## Reproduce

Run all deterministic checks from the artifact root:

```bash
python scripts/reproduce_all.py
```

Add `--include-scaling` to regenerate the machine-specific timing file.

Expected final output:

```text
all_deterministic_checks=PASS
machine_scaling_rerun=NO
```

The equivalent individual commands are:

```bash
python scripts/run_controlled_checks.py
python scripts/run_production_evidence_audit.py
python scripts/run_gnosis_counterfactual.py
python scripts/verify_certificate.py \
  --snapshot data/shutter_keyper_snapshot.json \
  --ledger data/evidence_ledger_public_only.csv \
  --target 10000
python scripts/verify_certificate.py \
  --snapshot data/shutter_keyper_snapshot.json \
  --ledger data/evidence_ledger_controlled_positive.csv \
  --target 10000
python deployment/scripts/verify_chiado_certificate.py
python scripts/run_scaling_benchmark.py
python scripts/run_lattice_mobius_experiments.py
python -m unittest discover -s tests -v
```

Run the three added experiments separately:

```bash
python extended_experiments/reproduce_extended.py
```

Expected final output: `extended_experiments=PASS`.

To check the deterministic experiment summary exactly:

```bash
python scripts/run_lattice_mobius_experiments.py > lattice_mobius_summary.txt
python -c "from pathlib import Path; assert Path('lattice_mobius_summary.txt').read_bytes() == Path('expected/lattice_mobius_summary.txt').read_bytes()"
```

The lattice/Möbius runner uses the fixed seed `20260714`. Its CSV outputs are
deterministic. The wall-clock and memory columns in `results/solver_scaling.csv`
are machine-specific. The supplied one-off run, ten repeat files, and their
deterministic summary are retained with hardware metadata. Rerunning with
`--include-scaling` changes the machine-specific file and therefore requires
regenerating `MANIFEST.sha256` with
`python scripts/verify_manifest.py --write` before redistributing the artifact.

## Recorded public-testnet execution certificate

The deployment source has a separate acceptance command:

```bash
cd deployment
npm ci
npm run verify
```

That command verifies the machine-readable Chiado certificate, runs static and
TypeScript checks, and runs seven Solidity/Hardhat tests. The complete Rolling
Shutter and Chiado procedure is in
`deployment/README.md`. On Windows it starts from the PyCharm PowerShell
terminal with:

```powershell
powershell -ExecutionPolicy Bypass -File .\deployment\rolling-shutter\run-in-wsl.ps1
```

The local contract harness is not accepted as deployment evidence. This final
artifact also contains the four machine records from the completed public run:
`deployment-chiado.json`, `job-chiado.json`, `shutter-evidence.json`, and
`slashing-chiado.json`. See `deployment/results/PUBLIC_RUN.md` for their
cross-record summary and public explorer links.

The certificate can be checked offline, without trusting the prose summary:

```bash
cd deployment
python scripts/verify_chiado_certificate.py
```

It recomputes the sum of the four smallest bond balances before and after the
recorded slashing, validates all cross-record identities and hashes, and checks
SHA-256 bindings to the contract, exporter, Keyper set, live verifier, and run
records. The expected result is a positive controlled-scope value of
`3,000,000,000,000` wei and
`production_shutter_certificate=NOT_CERTIFIED`.

The recorded public run can also be checked directly against current Chiado
RPC state without a private key:

```powershell
cd deployment
$env:CHIADO_RPC_URL = "https://rpc.chiado.gnosis.gateway.fm"
npm run verify:chiado:live
```

The offline certificate and live-chain verifier serve different purposes. The
offline command establishes deterministic record binding and exact calculation;
the live command establishes that the recorded transactions, bytecode, event,
and contract state are present on Chiado.

## Production deployment evidence audit

The production audit is a separate real-deployment case, not a controlled
profile. It fixes `2026-06-13T00:00:00Z` to Gnosis block `46,666,718` (hash
`0x574ec26ee7b2e2bfddd991bf99d37a79455428bc4dfe342b0ccf55d071229b60`),
then binds Keyper-set index 10, contract
`0xE817E77109e2E6a8025eB30dB3542eC18bBDE828`, threshold four, and the seven
member addresses. Run the deterministic audit with:

```bash
python scripts/run_production_evidence_audit.py
```

The recorded result has seven verified membership rows but zero positive
certified member floors. For every member, the result distinguishes unknown
actual resistance from a zero evidence-supported lower bound and records two
ways to make the row positive: a directly audited positive resistance floor,
or a complete attribution--forfeiture--execution path with a positive nominal
amount and joint probability floor. Activation evidence is audited separately
because it can upgrade the activation-respecting branch but cannot be exported
to package acquisition.

For a four-of-seven threshold, a positive threshold-cover certificate requires
strictly positive certified floors for at least four members. A target `B`
requires the sum of the four smallest member floors to be at least `B`. The
current audit therefore reports `additional_positive_member_floors_needed=4`;
it does not assert that actual resistance is zero.

With a reachable archival Gnosis RPC, recheck the frozen state and the
`KeyperSetAdded` and creation receipts:

```bash
python scripts/verify_production_snapshot_live.py
```

## Deterministic counterfactual on the pinned geometry

Run the small offline branch check with:

```bash
python scripts/run_gnosis_counterfactual.py
```

It retains the verified seven-member, four-of-seven Gnosis committee geometry
but places the hypothetical floors `R=[4,4,1,1,1,1,1]` and
`tau=[0,0,2/7,2/7,2/7,2/7,2/7]` in the separate counterfactual ledger
`I_cf`, using normalized cost units rather than estimates. The unified solver records public `0`,
resistance-only TC `4` with cover `{2,3,4,5}`, activation AC `10` with witness
`(0,1,2,3)`, and robust fallback `4` when either the ordered-witness or
exposure-sufficiency gate is disabled. All 21 placements of the two seed
members reproduce `(TC=4, AC=10)`.

This is a **deterministic counterfactual check on the pinned committee
geometry**. It is not a Gnosis activation experiment, production validation,
or measured Keyper resistance. It performs no chain write and does not rerun
the Chiado pilot.

## Lattice and Möbius outputs

- `results/mobius_pure_kway.csv`: exact checks of the coordinated-defense
  construction. All nonempty proper Möbius coefficients must be zero and only
  the full-order coefficient may be nonzero.
- `results/mobius_truncation.csv`: error at the full defense set after retaining
  only interactions below order `k`.
- `results/mobius_random_order_mass.csv`: interaction mass by order for 100
  seeded random uniform four-of-seven certificate instances.
- `results/mobius_random_truncation.csv`: first-, second-, and third-order
  truncation errors on those instances.
- `results/lattice_target_summary.csv`: number and minimum size of irreducible
  remediation plans for a seeded target.
- `results/uniform_allocation_algorithms.csv`: exact versus singleton-marginal
  greedy allocation on the random four-of-seven instances.
- `results/greedy_decoy_failure.csv`: a fixed-family construction in which
  positive-marginal decoys divert greedy allocation from a coordinated optimum.
- `results/defensive_allocation.csv`: computed member-level increment vectors,
  four minimal-cover costs, and the resulting certificate for every controlled
  allocation strategy and budget.
- `results/defensive_allocation_summary.csv`: the compact table view used in
  the paper.
- `results/penalty_certificate_checks.csv`: complete versus incomplete
  penalty-attribution evidence in controlled four-of-seven ledgers.
- `results/production_member_evidence_audit.csv`: all seven production member
  addresses, computed direct/penalty/compensation contributions, activation
  status, and the exact missing evidence on each path.
- `results/production_evidence_audit.json`: machine-readable pinned snapshot,
  certificate, per-member evidence gaps, minimum positive-member count, target
  condition, and non-transfer rule for the Chiado pilot.
- `results/dune_validation.csv`: deterministic consistency checks over the
  supplied Dune exports.
- `results/dune_calibration_summary.csv`: clearly labeled historical
  calibration metrics from the two distinct Dune method families.
- `extended_experiments/results/scalability_analysis.csv`: committee size, exact subset-state count,
  and median/IQR/range runtime from the ten retained benchmark repeats.
- `extended_experiments/results/certificate_cost_models.csv`: operation-growth comparison between
  sorted uniform threshold-cover evaluation and generic subset-state search.
- `extended_experiments/results/parameter_sensitivity.csv`: 48 controlled combinations of threshold,
  resistance shape, and initial exposure.
- `extended_experiments/results/baseline_comparison.csv`: public-only, minimum-member-floor,
  exact-lower-tail, and mean-resistance heuristic outputs, with certification
  status recorded explicitly.

## Interpretation boundary

The production experiment now audits the actual seven-member set at a pinned
historical block. It verifies committee state and then evaluates each member's
retained resistance, activation, attribution, execution, and compensation
evidence. Its result is a falsifiable evidence-gap finding: four additional
positive member floors are necessary for any positive four-of-seven
certificate, and each row states which auditable material would change it.
The controlled positive ledger remains only a verifier fixture.

The new sensitivity and baseline tables use normalized controlled resistance
profiles with equal mean resistance. They identify structural dependence on
threshold, exposure, and lower-tail shape; they are not measurements of live
Keyper resistance. The runtime table reports the supplied laptop repeats and
is an implementation benchmark rather than a hardware-independent complexity
claim.

The lattice and Möbius experiments are theorem and algorithm checks over
controlled or seeded instances. They do not turn the public Shutter snapshot
into a positive deployment certificate. The greedy-decoy experiment uses a
certified fixed outer family; it does not claim that this family has been
observed in the live deployment.

The Dune files have incomplete archival provenance: their original archive did
not include query SQL, execution IDs, retrieval timestamps, or fixed block
hashes. The transfer-join and dex.trades outputs use different methods and
sample sizes and are therefore reported separately. Historical notional and
coverage values are not a worst-case early-information value cap.

The controlled public Chiado experiment is complete. It deployed contract
`0x3C16dd5689D67d51c076fe80CB7189041c107721`, recorded a seven-share 4-of-7
Rolling Shutter evidence set, and submitted successful slashing transaction
`0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd`.
The certified bond floor changed from `4,000,000,000,000` to
`3,000,000,000,000` wei after member 0 was slashed.

This is a single-host controlled testnet experiment, not a production
deployment or evidence of seven independent organizations. The contract is
verifier-gated: the pinned Go verifier validates BLS shares, native Keyper
signatures, the aggregate key, and 4-share reconstruction; Solidity validates
the verifier's EIP-712 attestation, timing, bond transfer, and certificate
update. The controlled positive ledgers remain separate from public production
resistance evidence.
