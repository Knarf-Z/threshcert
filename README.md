# ThreshCert complete experiment bundle

ThreshCert is a reproducible artifact for distinguishing a contract charge
from the requesting attacker's authenticated relative-process net cost. The
current main result is a controlled positive certificate over one fixed
threshold-service composition:

```text
AUTHENTICATED-RELATIVE-PROCESS-CERTIFIED(4)
```

The result covers all 35 admitted successful routes through first
commitment-valid plaintext delivery. It is relative to the declared local
control boundary, settlement closure, runtime, and route language. It is not a
production-wide, Internet-wide, or unconditional economic-cost claim.

The repository also preserves the production evidence audit, controlled
countermodels, public Chiado records, finite-language experiments, exact
solvers, defense studies, and earlier integration packages. Preserved packages
remain separated from the current result so that their different claim domains
and accounting units are not conflated.

Authors: Jiaqi Zhang
([ORCID 0009-0005-3271-3106](https://orcid.org/0009-0005-3271-3106)) and
Honghao Fu
([ORCID 0000-0002-1934-3391](https://orcid.org/0000-0002-1934-3391)).
See `CITATION.cff` for machine-readable citation metadata and `HARDENING.md`
for how the verification layers fit together.

It intentionally excludes manuscript sources, virtual environments, IDE
metadata, `.env` files, private keys, dealer seeds, private host material, and
raw execution secrets.

`RESULTS_SUMMARY.md` gives the compact reproduced findings. `EXPERIMENTS.md`
defines every experiment and its interpretation boundary.

## Current auditable release

The v2 process certificate exposes the review-critical objects as
machine-readable data rather than prose-only assertions:

| Review requirement | Public artifact |
| --- | --- |
| Narrow claim | `claim_type=authenticated-relative-process-cost` and the exact quantity are stored in the v2 certificate. |
| Declared process model | The certificate records the attacker control boundary, represented real-success histories, checked routes, and the observation projection corresponding to `Ctrl(A)`, `H_real`, `R_Theta`, and `Obs_J`. |
| P5 completeness | Forward totality, whole-process reverse replay, same-session continuity, and cost preservation are explicit fields; minimum equality is not accepted as a premise. |
| Machine-readable certificate | `artifact/ope_process_positive/schema/ope_process_certificate.schema.json` defines the public JSON format. |
| Independent checking | `artifact/ope_process_positive/verify_process_certificate.py` uses only the Python standard library and does not import the generator or runtime implementation. |
| Cost-domain consistency | `artifact/COST_DOMAIN_REGISTRY.json` explains why the current value 4 and historical value 10 are from different, non-comparable domains. |
| Size and scaling | `artifact/ope_process_positive/results/verifier_benchmark.v1.json` reports the 625,243-byte certificate and 1/5/10/20/35-route verification measurements. Prefix measurements are explicitly non-certifying. |
| Anonymous review package | `artifact/anonymous_v16/anonymous_v16_artifact.zip` contains an author-free review bundle with its own manifest and one-command reproduction entry. |

The independent verifier checks 35/35 routes, 140/140 operator signatures,
140/140 Chaum--Pedersen proofs, threshold reconstruction, delivery,
settlement-linked accounting, source bindings, and the committed negative
controls. The mathematical definitions still belong in the paper; this
repository provides their executable representation and audit trail.

Quick verification from the repository root:

```bash
python reproduce_v16_experiments.py
```

The anonymous ZIP currently has SHA-256
`ccaf4b717f20ade9b439ff243a5bcfe878f6d7e1311c3b1c9df92c9462db7f01`.
The named GitHub repository is not itself an anonymous submission channel.

## Contents

- `scripts/run_floor_admission_experiment.py`: rejects unsupported or inflated
  floor reports and admits only member-bound, automatically forfeitable value
  net of certified recovery and reimbursement caps; it records seven scenarios,
  10,000 seeded soundness checks, and all 128 disclosure subsets.
- `scripts/run_refresh_window_experiment.py`: compares persistent and
  refresh-erased shares under identical per-epoch ledgers, then checks duration
  monotonicity and epoch decomposition on 5,000 seeded instances.
- `results/floor_admission_experiment.json` and
  `results/refresh_window_experiment.json`: canonical machine-readable outputs
  for those two experiments.

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
- `data/gnosis_counterfactual_fixture.json`: a legacy-named but separate
  equal-cost weighted counterfactual ledger on seven members and threshold
  `4/7`. All member floors are one; its weights and operational gates are
  hypothetical and do not reuse production Gnosis weight geometry.
- `scripts/run_gnosis_counterfactual.py`: sends that fixture through the exact
  weighted threshold-cover and subset-state solvers and the certificate gates,
  including all 210 assignments of two prerequisite and two core roles.
- `results/gnosis_counterfactual_result.json`: records public `0`, TC `2`, AC
  `4`, gate-rejected fallback `2`, and witnesses with the non-production
  claim boundary.
- `tests/test_gnosis_counterfactual.py`: verifies the cardinality/threshold
  binding, witnesses, role-assignment invariance, gate fallback, and portable
  JSON bytes.
- `data/evidence_ledger_public_only.csv`: address-level compatibility view of
  the production audit for the basic threshold-cover verifier.
- `data/evidence_ledger_controlled_positive.csv`: a controlled positive ledger used only to test the verifier. It is not deployment evidence.
- `scripts/verify_certificate.py`: computes the uniform threshold-cover certificate.
- `scripts/run_controlled_checks.py`: writes the equal-cost activation, fixed-uniform-cost mechanism-scope, defensive-allocation, and sensitivity outputs.
- `scripts/run_scaling_benchmark.py`: runs a machine-specific exact subset-state scaling check.
- `scripts/defense_lattice.py`: exact sequential solver, Boolean-lattice
  transforms, target-plan enumeration, and allocation utilities.
- `scripts/run_lattice_mobius_experiments.py`: writes the pure high-order,
  low-order truncation, random four-of-seven, target-lattice, and greedy-decoy
  results.
- `scripts/run_generalized_committee_sweep.py`: repeats the seeded random
  monotonicity, Möbius truncation-error, and exact-vs-greedy allocation checks
  at committee shapes 3-of-5, 5-of-9, 6-of-11, and 7-of-13, so the n=7
  findings above are not read as an artifact of the one committee size the
  paper headlines. Additive: it does not modify or rerun the n=7 experiment.
- `extended_experiments/`: self-contained scalability,
  certificate-computation cost, parameter-sensitivity, and baseline-comparison
  experiments with their own inputs, results, tests, and reproduction command.
  Its `parameter_sensitivity_boundary.csv` output covers degenerate threshold
  margins, an all-zero and a single-dominant-member resistance profile, and
  committee sizes 14 and 28, kept separate from the original 48-row table.
- `verification_scripts/`: an independent, from-scratch reimplementation built
  only from the paper's own formulas (not the authors' code), used to
  cross-check every named number in Section 7 and stress-test the central
  theorems beyond the paper's own hand-picked examples. See its own `README.md`.
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
- `trace_then_slash_phase2_chiado/`: the paper-matched 4-of-7
  TraceThenSlash mechanism, 14 adversarial tests, guarded three-instance
  Chiado deployment runner, and independent-RPC verifier for sequential,
  atomic, and repeated packaging.
- `joint_incidence_fixture/`: a separate finite 4-of-7 overlapping-pool
  residual-price mechanism. It classifies all \(3^7=2,187\) integer credit
  candidates, checks all \(117\times35=4,095\) admissible state--set pairs,
  and executes an exact 4-unit minimizer.
- `artifact/finite_toy_delivery_extension/`: a 10-state, 11-transition finite
  process model with separate service role and member identifiers, explicit
  finality and delivery events, two first-success routes, and four mutations.
- `artifact/process_route_stress_fixture/`: an OPE-receipt-anchored v2 process
  fixture with contract costs `(4,4,4)`, net costs `(4,3,0)`, five route
  exclusions, and three process-certificate mutations.
- `artifact/ope_process_positive/`: an executable OPE controlled composition
  with seven operator HTTP processes, 35/35 fixed-root routes, EIP-191 buyer
  authentication, six-confirmation finality, four verified responses per
  route, commitment-valid delivery, closed return interfaces, and verdict
  `AUTHENTICATED-RELATIVE-PROCESS-CERTIFIED(4)`.
- `artifact/paid_threshold_response_two_host_v6/`: the verified,
  privacy-scrubbed public release of the earlier controlled two-host
  integration, including frozen source, tests, certificate checkers, and
  canonical evidence. Its finite-language value of 10 is supplementary and
  is not the current OPE relative-process result.
- `artifact/fc_experiment_upgrade_v4_2/`: the preserved v4.2 experiment suite
  for pinned and longitudinal Keyper-set audits, atomic bypass,
  replacement-hull classification, and evidence sensitivity. It is retained
  for completeness and is not presented as new production evidence.

## Reproduce

For the complete v16 experiment set, including the nontrivial positive OPE
process certificate, run:

```bash
python reproduce_v16_experiments.py
```

Expected final lines include `V16_AUTHENTICATED_RELATIVE_PROCESS_CERTIFICATE=PASS`. This regenerates all
35 fixed-configuration OPE executions, verifies 35 buyer signatures, starts
seven operator processes, verifies 140 threshold responses, replays all 35
complete process routes, and checks the negative controls. The claim is
relative to the admitted local composition; it is not a production or
deployment-global attacker-cost claim.

The current machine verdict is explicitly narrowed to:

```text
AUTHENTICATED-RELATIVE-PROCESS-CERTIFIED(4)
```

The same command validates the public JSON Schema, runs the separately written
standard-library verifier, and checks the committed size/scaling benchmark.
The verifier can also be run directly:

```bash
python artifact/ope_process_positive/verify_process_certificate.py
python artifact/ope_process_positive/benchmark_certificate_verifier.py --verify
```

The two supplementary packages have independent checks. Verify the scrubbed
two-host archive and its source tests with:

```bash
python artifact/paid_threshold_response_two_host_v6/extracted/project/scripts/export_public_release.py --verify-only artifact/paid_threshold_response_two_host_v6/frozen/two_host_execution_evidence.v68.public.zip
python artifact/paid_threshold_response_two_host_v6/run_public_tests.py
```

On Windows, rerun the preserved FC v4.2 suite with:

```powershell
cd artifact\fc_experiment_upgrade_v4_2
.\setup.ps1
.\run_all.ps1
```

Its optional live historical audit performs read-only RPC calls; the default
run uses the committed fixture and requires no network access. The apparent
values 4 and 10 belong to different claim domains; see
`artifact/COST_DOMAIN_REGISTRY.json`.

Build and verify the author-free review bundle with:

```bash
python build_anonymous_artifact_v16.py
python build_anonymous_artifact_v16.py --verify-only
```

The resulting `artifact/anonymous_v16/anonymous_v16_artifact.zip` contains a
standalone `reproduce.py`, an internal SHA-256 manifest, and no manuscript,
citation metadata, repository history, account credentials, or private host
material. Hosting the ZIP on the review venue is still required for genuinely
anonymous distribution; the named GitHub repository itself is not anonymous.

For the v77 review certificate, run the single public entry below. It checks
the committed manifests, installs the locked EVM dependencies, and executes
the C6/B5 certificates, finite-world global certificate, negative controls,
18 EVM tests, deployment admission, and refinement checks:

```bash
python reproduce_v77.py
```

Expected final line: `v77_public_review_artifact=PASS`. The command is offline
after `npm ci` has obtained the lockfile-pinned dependencies; it performs no
public-chain write and does not contain or reproduce the paper.

Run every offline, deterministic check from one entry point:

```bash
python reproduce_everything.py
```

Expected final line: `everything=PASS`. This chains the four layers below,
which also remain independently runnable.

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
python scripts/run_floor_admission_experiment.py
python scripts/run_refresh_window_experiment.py
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

Run the generalized committee-shape sweep separately (additive, does not
rerun the n=7 experiment above):

```bash
python scripts/run_generalized_committee_sweep.py
```

Run the three added scalability/sensitivity/baseline experiments separately:

```bash
python extended_experiments/reproduce_extended.py
```

Expected final output: `extended_experiments=PASS`.

Run the independent from-scratch verification suite separately:

```bash
cd verification_scripts
python test_equivalence.py
python reproduce_paper_numbers.py
python hardening_and_greedy.py
python instability.py
python scaling_fast.py --ns 8 10 12 14 16 18
```

See `verification_scripts/README.md` for what each script checks and its
honest limitations.

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
and contract state are present on Chiado. As last run (2026-07-20), both the
live Chiado check and the live Gnosis production-snapshot recheck below still
returned `PASS` against current chain state.

## TraceThenSlash Phase 2 package

The separate `trace_then_slash_phase2_chiado/` package upgrades the defensive
experiment to member-bound, nonreplayable enforcement whose certificate is
independent of sequential, atomic, or repeated submission boundaries:

```bash
cd trace_then_slash_phase2_chiado
npm ci
npm run ready
```

The readiness command compiles the exact Solidity contract, performs strict
TypeScript checking, and runs 14 adversarial tests, including the complete
`24 x 8 = 192` order-partition product and package sizes 1--7. The guarded
public-run default uses 0.002 xDAI per member: three contracts commit
0.042 xDAI of principal, reserve 0.02 xDAI for gas, and enforce a separate
0.1-xDAI principal cap. The deployment and independent verification commands
are documented in the package README.

No Phase 2 public-chain result is committed yet. The directory is
deployment-ready source and verification logic; it does not replace the
already recorded one-share Chiado pilot or turn the controlled 8-unit
enforcement-loss result into an unconditional attacker-payment certificate.

## Finite joint-incidence fixture

The separate `joint_incidence_fixture/` package implements a controlled
four-of-seven public-state residual-price mechanism with two overlapping
cap-2 credit pools. Each member has gross floor 2, contract credits are
restricted to 0, 1, or 2 units, and acquiring four distinct members requires
exact residual payment `2 - credit` to each selected member.

```bash
cd joint_incidence_fixture
npm ci --no-audit --no-fund
npm run ready
npm run manifest:check
```

The tests exhaustively classify all 2,187 integer candidates, verify that
exactly 117 states satisfy both pool caps, compare every one of the 4,095
admissible contract quotes with an independently evaluated arithmetic sum,
and execute a 4-unit minimizing transaction. The fixture establishes the
declared finite state--set relation and payment equality at contract level.
It does not establish ultimate beneficial ownership or attacker-independence
of the pool funds, production member costs, or a real collusion price.
## Finite global named-acquirer certificate (v77)

The v77 artifact adds a separate positive instance whose complete declared toy
world contains four accounts, a singleton buyer control closure, explicit initial
balances, no external-funding or return events, and five possible actions. The
Solidity harness requires a five-ether-denominated simulated debit before two
fixed members can certify a buyer/resource-bound output. An independent Python
checker enumerates all 8 reachable states, 9 enabled transitions, and both
first-success routes; B1--B5 all pass and the result is
`GLOBAL-NAMED-ACQUIRER-CERTIFIED(5000000000000000000)` simulated wei.

```powershell
cd artifact\joint_incidence_refinement
npm ci --no-audit --no-fund
npm run typecheck
npm test
py -3.11 ..\global_named_acquirer_toy\verify_global_named_acquirer_toy.py --verify --self-test
```

Six single-gate negative controls and two interface-ablation cases are committed.
In each ablation, equating a positive contract-local debit with global payment
would falsely emit `CERTIFIED(g)`; sponsor funding or a complete return instead
makes the typed global floor zero. The positive result is therefore global only
inside the fully enumerated finite toy world, not a production or Internet-wide
beneficial-control claim.

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

## Deterministic equal-cost weighted counterfactual

Run the small offline branch check with:

```bash
python scripts/run_gnosis_counterfactual.py
python scripts/run_floor_admission_experiment.py
python scripts/run_refresh_window_experiment.py
```

The separate ledger `I_cf` has seven members, threshold `4/7`, weights
`[2/7,2/7,2/21,2/21,2/21,1/14,1/14]`, one-unit floors for every
member, and gates `[1/7,1/7,1/7,1/7,1/7,0,0]`. The exact solvers
record public `0`, resistance-only TC `2` with cover `{0,1}`,
activation AC `4` with witness `(5,6,0,1)`, and robust fallback
`2` when either activation gate is disabled. All 210 assignments of the
two prerequisite and two core roles reproduce `(TC=2, AC=4)`.

Every member has the same floor. The difference counts two additional
prerequisite acquisitions under stipulated operational gates; it does not
model an attacker choosing higher-priced members first. The fixture is not a
Gnosis activation experiment, production validation, or measured Keyper
resistance. It performs no chain write and does not rerun the Chiado pilot.

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
- `results/mobius_generalized_sweep.csv`: monotonicity and first/second/third-
  order truncation error at committee shapes 3-of-5, 5-of-9, 6-of-11, and
  7-of-13, 100 seeded trials each.
- `results/allocation_generalized_sweep.csv`: exact-versus-greedy allocation
  gain ratios at the same generalized committee shapes and budgets one
  through three.
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
- `extended_experiments/results/parameter_sensitivity_boundary.csv`: 64 rows covering degenerate
  threshold margins (q=1, q=7), an all-zero and a single-dominant-member
  resistance profile, and committee sizes 14 and 28.
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
claim. The boundary and larger-committee rows are the same normalized-profile
construction taken to its parameter extremes; they do not introduce new
production evidence either.

The generalized committee-shape sweep is the same seeded-random-instance
construction as the n=7 experiment, run at four additional shapes. It shows
the monotonicity and truncation-error findings are not specific to 4-of-7; it
is not a claim about any real committee of those other sizes.

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
