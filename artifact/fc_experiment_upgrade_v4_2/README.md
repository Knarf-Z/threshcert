# FC Experiment Upgrade Package v4.2

This package adds five experiments for the paper:

1. pinned Keyper-set evidence audit;
2. live, event-backed inventory of all 11 production Keyper-set rotations;
3. one-shot and repeated atomic-bypass experiments;
4. replacement-hull LP classification and numerical stress tests;
5. evidence omission and false-certification sensitivity.

## Windows installation

Open PowerShell in the extracted package and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
.\run_all.ps1
```

To place the project at the requested location:

```powershell
.\install_to_d.ps1
cd D:\paper_project\fc_experiment_upgrade
.\setup.ps1
.\run_all.ps1
```

Outputs are written to `results\`. The default run is deterministic and does
not require network access. It uses the pinned 4-of-7 committee fixture from
the paper.

## Live historical audit

The package now contains the full production manager address, pinned snapshot
hash, event topic, and expected set count recovered from the retained
production artifact. After the deterministic run, execute:

```powershell
.\run_live_audit.ps1
```

The script queries chain ID 100 at block `46,666,718`, checks the pinned block
hash, reads every manager set, checks its state, and independently decodes the
matching `KeyperSetAdded` event. Set 10 additionally carries the retained
period-matched public evidence audit. Sets 0--9 deliberately report
`NOT_EVALUATED_MISSING_PERIOD_EVIDENCE`; missing evidence is not rewritten as
zero.

## Atomic contract

The Python experiment always runs. If Foundry is installed, `run_all.ps1` also
runs the Solidity tests:

```powershell
cd contracts
forge test -vv
```

The contract demonstrates atomic all-or-nothing payment and a global invocation
budget. Acceptance is gated by a pluggable `IShareVerifier`.
`AttestedShareVerifier.sol` adds an executable verification boundary: native
Rolling Shutter share, signature, and reconstruction checks remain off chain;
the contract verifies a replay-resistant typed attestation bound to the chain,
verifier, escrow, offer, member, and share hash. See
`SHARE_VERIFICATION_BOUNDARY.md`. The experiment does not claim that real
Keypers accept these offers.

## Main outputs

- `results/pinned_snapshot_audit.csv`
- `results/pinned_snapshot_audit.json`
- `results/pinned_snapshot_audit_summary.json`
- `results/historical_keyper_sets.csv` (after `run_live_audit.ps1`)
- `results/historical_keyper_sets.json` (after `run_live_audit.ps1`)
- `results/historical_keyper_sets_summary.json` (after `run_live_audit.ps1`)
- `results/atomic_bypass_curve.csv`
- `results/atomic_bypass_repetition.csv`
- `results/replacement_hull_trials.csv`
- `results/replacement_hull_tolerance_sweep.csv`
- `results/replacement_hull_summary.json`
- `results/evidence_sensitivity.csv`
- `results/evidence_sensitivity_summary.json`
- `results/environment.json`
- `results/python_test_output.txt`
- `results/foundry_version.txt`
- `results/foundry_test_output.txt`
- `results/run_manifest.json`

## Interpretation limits

- A zero production certificate means no retained positive public floor, not
  zero private resistance.
- The live audit supports a longitudinal committee-configuration claim when
  all 11 states and events verify. It does not support a longitudinal
  resistance-certificate claim: the older periods lack period-matched public
  floor evidence.
- Contract execution establishes mechanism feasibility, not willingness to
  collude. The attestation adapter establishes an executable boundary, not
  direct on-chain BLS verification or an audit of the off-chain attester.
- LP classifications near the hull boundary must be reported with their
  separation distance and numerical tolerance.

## Version 4 additions

- full production manager, snapshot, event, and set-10 provenance values;
- live decoding and cross-checking of all historical `KeyperSetAdded` events;
- an explicit split between longitudinal committee evidence and period-specific
  resistance evidence;
- an EIP-712-style attested-share adapter with canonical ECDSA recovery;
- replay tests binding the proof to the share, member, offer, and escrow;
- 20 Foundry adversarial/unit tests and 17 Python tests are expected.

## Version 4.1 correction

- the event locator now checks a short post-activation window because
  production set 0 emitted `KeyperSetAdded` one block after its recorded
  activation block;
- RPC reads are batched per set, transport failures use bounded exponential
  retry, and each verified set is printed as progress.

## Version 4.2 metadata correction

- `environment.json` now reads the package version from `VERSION` instead of a
  stale hard-coded v3 string;
- a regression test enforces agreement between the environment report and the
  package version;
- `repair_metadata.ps1` refreshes the environment report, Python test output,
  and manifest without rerunning or deleting the successful live-chain audit.
