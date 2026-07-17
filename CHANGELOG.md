# Artifact update: defense lattice and Möbius experiments

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

The production public-only Shutter snapshot continues to support a zero
certificate. The completed single-host controlled pilot is a separate
implementation experiment and does not establish production resistance values
or independent operator governance.
