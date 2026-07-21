# ThreshCert artifact changelog

## 2026-07-21 second upgrade pass

- Extended the generalized committee-shape sweep
  (`scripts/run_generalized_committee_sweep.py`) with two more shapes,
  8-of-15 and 9-of-17 (100 trials each), continuing the existing
  `(5,3),(9,5),(11,6),(13,7)` progression. Purely additive: each shape's
  random draws are independently seeded by `(n, q)`, so the four
  previously-recorded shapes and the original n=7 experiment are unchanged;
  confirmed by rerunning and diffing the four original shapes' printed
  values. Both new shapes were monotone across all 100 trials and greedy
  was exact at budget one and two, degrading at budget three -- the same
  qualitative pattern as the existing four shapes.
- Added a new parallel scaling point, `n=20`, to the machine-specific exact-
  solver benchmark (`scripts/run_scaling_benchmark_extended.py` +
  `scripts/summarize_scaling_repeats_extended.py`), with its own ten-repeat
  raw files and median/IQR summary
  (`results/solver_scaling_repeats_extended*`). Kept separate from
  `scripts/run_scaling_benchmark.py`'s existing n=8..18 table because that
  table's file/row counts are hard-asserted and its summary is consumed
  (byte-compared) by `extended_experiments/`. Median wall time `32.244088` s,
  consistent with the existing growth trend.
- Actually ran and recorded (rather than just documenting as possible) the
  independent-implementation scaling check
  (`verification_scripts/scaling_fast.py`) through n=24, saving the full
  n=8..24 table to the new `verification_scripts/results/scaling_fast_extended.txt`
  (n=24: 16,777,216 states, median 55.99 s).
- Neither new scaling script joins the automatic `reproduce_everything.py`
  chain, consistent with the existing exclusion of machine-specific timing
  benchmarks from that chain.
- Received the paper's full `main_text.tex` directly from the author and
  saved it to `paper/main_text.tex`, closing the "paper source not on this
  machine" gap noted for every theorem except the replacement-hull one
  (confirmed the previously pasted replacement-hull theorem statement
  matches `main_text.tex` exactly; `appendix_route_b.tex`, containing the
  proofs, is still not present).
- Added `verification_scripts/information_boundary.py`, independently
  stress-testing the paper's central theorem (evidence-optimal certificates
  under activation scope). Unlike `test_equivalence.py` (which checks the
  (AC) reduction for one fixed profile), this tests the theorem's actual
  claim about an evidence ledger: on 300 random small instances (n=3..7),
  the exact-floor profile attains TCR/ACR exactly (tightness), and 1,500
  further profiles built strictly above the same floors -- resistance and
  activation independently perturbed upward, including the
  most-permissive all-zero-tau case for the mechanism-robust TCR claim --
  never certified a smaller attack cost (soundness); a separate 60-instance
  check confirms the public-only layer collapses to exactly zero. Not part
  of the routine reproduction chain (same tier as `replacement_hull.py` and
  `scaling_fast.py`).

## 2026-07-20 pre-submission hardening pass

- Merged this working tree with the parallel `FC_complete_experiment_bundle`
  distribution, which had independently gained an independent from-scratch
  reimplementation (`verification_scripts/`) that cross-checks the paper's
  own numbers; that suite was ported in, and this tree's production evidence
  audit, Gnosis counterfactual, and Chiado execution certificate were ported
  the other way so both stay at feature parity.
- Added a generalized committee-shape sweep
  (`scripts/run_generalized_committee_sweep.py`) that repeats the seeded
  random monotonicity, Möbius truncation-error, and exact-vs-greedy
  allocation checks at four additional committee shapes (3-of-5, 5-of-9,
  6-of-11, 7-of-13, 100 trials each), so the n=7 findings are not read as an
  artifact of the one committee size the paper headlines. Truncation error is
  computed via a per-order zeta-transform accumulation rather than the
  original `O(3^n)` per-mask routine, keeping the check cheap up to n=13; the
  faster routine was cross-checked exactly against the original for `0`
  mismatches on a held-out instance.
- Added a boundary and larger-committee sensitivity sweep to
  `extended_experiments/` (`parameter_sensitivity_boundary.csv`, 64 rows):
  degenerate threshold margins (`q=1`, `q=7`), an all-zero and a
  single-dominant-member resistance profile, and committee sizes 14 and 28
  built by tiling the original profile shapes. Kept separate from the
  existing 48-row table so its row count and recorded numbers are unchanged.
- Added `reproduce_everything.py` at the artifact root, chaining the four
  previously separate reproduction entry points
  (`scripts/reproduce_all.py`, the new generalized sweep,
  `extended_experiments/reproduce_extended.py`, and the
  `verification_scripts/` suite) plus the offline Chiado certificate check
  into one `everything=PASS` command.
- Re-ran the live production-snapshot recheck and the live Chiado recheck;
  both still returned `PASS` against current chain state as of this pass.
- Added `verification_scripts/replacement_hull.py`, closing the one
  previously-unexercised item in that suite's own limitations list: the
  replacement-hull attribution theorem (public-attribution-formal-bounds),
  from the theorem statement supplied directly by the paper's author since
  `main_text.tex` is not on this machine. Checks the primal (lambda) formula
  against the equivalent (s, Q in conv(R)) formula for `A_i^eps(C,x)` on 200
  random instances via an exact Fraction-equality check (not tolerance-based:
  extracts `s*` from the primal LP's own optimal solution and independently
  re-solves the other formula's inner problem at that exact value), plus the
  separation corollary on three hand-picked constructive instances. Not part
  of the routine reproduction chain (takes ~45 seconds; run separately, like
  `scaling_fast.py`).
- Regenerated `MANIFEST.sha256` after the merge and additions; every
  reproduction layer, including the seven-test deployment suite, passes.

## 2026-07-19 pinned-geometry counterfactual branch check

- Added a deterministic seven-member, four-of-seven counterfactual fixture
  bound to the pinned Gnosis committee geometry, with explicitly hypothetical
  resistance and activation floors in normalized cost units and a separate
  counterfactual ledger.
- Added strictly conditional paper language for the `0 -> 4 -> 10` evidence
  layers, plus synchronized limitations and conclusion language; the actual
  production ledger remains zero.
- Ran the existing exact subset-state solver through the public, TC, AC, and
  robust-fallback branches, recording `0 -> 4 -> 10 -> 4`, TC cover
  `{2,3,4,5}`, and AC witness `(0,1,2,3)`.
- Checked all 21 seed-member placements and verified that disabling either the
  ordered-witness or exposure-sufficiency gate suppresses the AC value and
  returns the separable-payment TC fallback of `4`.
- Added a portable result JSON, exact expected stdout, five regression tests,
  and root-reproduction integration. No Chiado or production-chain experiment
  was rerun.
- Fixed the retained production-audit JSON writer to emit UTF-8/LF bytes on
  every operating system, preventing Windows/Linux manifest drift.

## 2026-07-19 production deployment evidence audit

- Replaced the date-only production snapshot with an archival anchor at Gnosis
  block `46,666,718` and recorded its hash, manager, active set, activation
  block, creation and registration transactions, threshold, and seven real
  member addresses.
- Added a seven-row evidence ledger covering direct resistance, activation,
  attribution, forfeiture, joint execution probability, and insurance or
  compensation for every production Keyper.
- Added deterministic evidence gates and per-member result files. The audit
  distinguishes unknown actual resistance from a zero certified floor and
  reports that four additional positive member floors are needed for any
  positive four-of-seven certificate.
- Added a standard-library archival-RPC verifier for the fixed block, set
  state, creation receipt, and `KeyperSetAdded` event.
- Integrated the production audit into the root reproduction command and added
  tests showing that unsupported numerical claims and nominal penalties cannot
  enter the certificate.

## 2026-07-19 machine-readable Chiado execution certificate

- Added a deterministic certificate that binds the recorded 4-of-7 Rolling
  Shutter evidence, Chiado transaction trail, contract, exporter, Keyper set,
  and live verifier by SHA-256.
- Added an offline verifier that recomputes the exact four-smallest-bonds value
  before and after slashing and rejects stale or cross-inconsistent records.
- Integrated certificate verification into the root reproduction command,
  bundle-integrity tests, and deployment acceptance command.
- Encoded the claim boundary inside the certificate: the `3e12`-wei value is
  positive within the controlled public-testnet mechanism, while production
  Shutter resistance, activation, and enforcement probability remain
  `NOT_CERTIFIED`.

## 2026-07-17 complete hardened bundle

- Fixed cross-version byte reproducibility for the four seeded random-lattice
  CSV files by making floating-point accumulation order explicit. The outputs
  now match the recorded Python 3.11 baseline when reproduced on Python 3.11
  or 3.12.
- Preserved the complete original experiment code and recorded results.
- Kept scalability, parameter sensitivity, and baseline comparison isolated in
  `extended_experiments/`.
- Added read-only Chiado verification of 11 transaction receipts, exact
  creation bytecode and constructor arguments, live committee state, slashing
  calldata, and the emitted event.
- Expanded Solidity tests to cover nonuniform bonds and binding of every
  verifier-signed evidence field.
- Expanded the Go evidence exporter checks for duplicate and out-of-range
  Keyper indices and stronger instance/eon/identity binding.
- Added public Dune query links while retaining the explicit limitation that
  the archived raw SQL was not included.
- Added citation metadata for Jiaqi Zhang and Honghao Fu.

## Earlier artifact update: defense lattice and Möbius experiments

## Added

- Exact Boolean-lattice Möbius and inverse transforms.
- Exact sequential solver for the coordinated-defense construction.
- Pure high-order interaction and low-order truncation experiments.
- One hundred seeded random uniform four-of-seven certificate instances.
- Exact versus singleton-marginal greedy allocation checks.
- A fixed-family decoy construction exposing arbitrarily poor greedy gain.
- Minimal target-achieving remediation-plan enumeration.
- Unit tests and a single deterministic reproduction entry point.
- Controlled penalty-evidence gate checks.
- Supplied Dune/GPv2 exports, provenance limitations, validation, and a
  calibration-only summary.
- A complete experiment inventory and explicit list of missing deployment
  artifacts.
- Ten retained exact-solver scaling repeats, hardware metadata, and a
  deterministic median/IQR summary.
- A seven-process 4-of-7 Rolling Shutter v1.4.4 deployment overlay with fresh
  runtime keys and DKG readiness checks.
- A Go evidence exporter that validates Shutter BLS shares, native Keyper
  signatures, aggregate-key validity, and four-share reconstruction.
- A verifier-gated bonded-Keyper Solidity contract, six Hardhat tests, and
  Chiado scripts that record the complete public transaction trail.

## Corrected

- Defensive-allocation values are now computed rather than copied from a
  documented table. The detailed output records every member increment and all
  four minimal-cover costs.
- Machine-specific scaling output is excluded from the immutable hash manifest.
- The activation-ladder exposure column no longer emits a binary floating-point
  representation such as `0.30000000000000004`.

## Completed public pilot

- Added the returned Chiado deployment, release-job, validated seven-share
  evidence, and slashing records from the completed user-run experiment.
- Recorded public contract
  `0x3C16dd5689D67d51c076fe80CB7189041c107721` and successful slashing
  transaction
  `0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd`.
- Added cross-record integrity tests and portable artifact references.

The production evidence audit supports a zero certified lower bound while
leaving actual resistance unknown. The completed single-host controlled pilot
is a separate implementation experiment and does not establish production
resistance values or independent operator governance.
