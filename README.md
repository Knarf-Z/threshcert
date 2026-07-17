# ThreshCert: Certifying the Economic Security of Threshold Committees

[![Reproducibility](https://img.shields.io/badge/reproducibility-passing-brightgreen)](#reproduce)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![Solidity](https://img.shields.io/badge/Solidity-Hardhat-363636)](deployment/)
[![GitHub stars](https://img.shields.io/github/stars/Knarf-Z/threshcert?style=social)](https://github.com/Knarf-Z/threshcert/stargazers)

**ThreshCert** is the reproducible artifact for studying and certifying the
economic security of threshold committees. It connects attack-cost
certificates, activation-aware acquisition, defensive allocation, Boolean
lattice interactions, and evidence-based slashing in one executable workflow.

The artifact combines deterministic Python experiments with a seven-process,
4-of-7 Rolling Shutter deployment, validation of seven decryption shares, and
a verifier-gated slashing transaction on the public Gnosis Chiado testnet.

## Highlights

- Exact certificate, activation, allocation, and defense-lattice experiments.
- Ten recorded solver-scaling repeats plus independent scalability,
  parameter-sensitivity, and baseline-comparison experiments.
- A seven-Keyper, seven-validator, 4-of-7 Rolling Shutter DKG on one host.
- Validation of seven BLS shares, native Keyper signatures, the stored
  aggregate key, and four-share key reconstruction.
- A public Chiado deployment whose certificate changed from
  `4000000000000` wei to `3000000000000` wei after successful evidence-based
  slashing.

## Public deployment evidence

- Contract: [`0x3C16dd5689D67d51c076fe80CB7189041c107721`](https://gnosis-chiado.blockscout.com/address/0x3C16dd5689D67d51c076fe80CB7189041c107721)
- Slashing transaction: [`0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd`](https://gnosis-chiado.blockscout.com/tx/0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd)
- Chain ID: `10200`
- Committee and threshold: `7` and `4`
- Slashing gas used: `108629`

Machine-readable deployment, release-job, evidence, and slashing records are
under [`deployment/results`](deployment/results/) and
[`deployment/evidence`](deployment/evidence/).

## Artifact boundaries

The seven Keypers are separate processes on one host, not seven independently
governed production operators. Controlled resistance ledgers test the
certificate machinery and are not claims about private production-member
costs. Historical Dune exports are calibration inputs, not member-level
resistance evidence.

`RESULTS_SUMMARY.md` summarizes the reproduced findings, while
`EXPERIMENTS.md` defines the full inventory and every interpretation boundary.

## Authors

- [Jiaqi Zhang](https://orcid.org/0009-0005-3271-3106)
- Honghao Fu

## Contents

- `data/shutter_keyper_snapshot.json`: the recorded public snapshot inputs. The archival block number and block hash are deliberately `null` because they were not recorded in the manuscript's original audit.
- `data/evidence_ledger_public_only.csv`: public threshold structure without member-level resistance evidence.
- `data/evidence_ledger_controlled_positive.csv`: a controlled positive ledger used only to test the verifier. It is not deployment evidence.
- `scripts/verify_certificate.py`: computes the uniform threshold-cover certificate.
- `scripts/run_controlled_checks.py`: writes the activation-ladder, mechanism-scope, defensive-allocation, and sensitivity outputs.
- `scripts/run_scaling_benchmark.py`: runs a machine-specific exact subset-state scaling check.
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
python scripts/verify_certificate.py \
  --snapshot data/shutter_keyper_snapshot.json \
  --ledger data/evidence_ledger_public_only.csv \
  --target 10000
python scripts/verify_certificate.py \
  --snapshot data/shutter_keyper_snapshot.json \
  --ledger data/evidence_ledger_controlled_positive.csv \
  --target 10000
python scripts/run_scaling_benchmark.py
python scripts/run_lattice_mobius_experiments.py
python -m unittest discover -s tests -v
```

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
regenerating `MANIFEST.sha256` before redistributing the artifact.

## Real-deployment pilot

The deployment source has a separate acceptance command:

```bash
cd deployment
npm ci
npm run verify
```

That command runs static checks, TypeScript checks, and six Solidity/Hardhat
tests. The complete Rolling Shutter and Chiado procedure is in
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
- `results/dune_validation.csv`: deterministic consistency checks over the
  supplied Dune exports.
- `results/dune_calibration_summary.csv`: clearly labeled historical
  calibration metrics from the two distinct Dune method families.

## Interpretation boundary

The controlled positive ledger proves that the verifier can output a positive certificate when certified resistance inputs are supplied. It does not prove that the Shutterized Gnosis Chain deployment currently has those inputs. A non-counterfactual positive deployment certificate requires public or institutionally auditable member-level evidence. No such evidence is fabricated here.

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

## Citation

If you use ThreshCert, please cite the repository metadata in
[`CITATION.cff`](CITATION.cff). GitHub's **Cite this repository** menu will
generate a formatted citation from that file.

```bibtex
@software{zhang_fu_2026_threshcert,
  author  = {Jiaqi Zhang and Honghao Fu},
  title   = {ThreshCert: Certifying the Economic Security of Threshold Committees},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/Knarf-Z/threshcert}
}
```
