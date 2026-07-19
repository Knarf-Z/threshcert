# ThreshCert artifact changelog

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
