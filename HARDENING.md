# Integrated hardening notes

This archive is a complete replacement distribution, not a patch-only package.
It combines the pinned production evidence audit, original deterministic
experiments and recorded public pilot artifacts, the separately runnable
`extended_experiments/` suite, and the 2026-07-17 verification hardening.

No historical timing sample, experiment CSV, public transaction record, or
validated evidence record was regenerated while assembling this archive.

The random-lattice generator uses an explicit left-to-right floating-point
accumulator. This avoids the change to floating-point `sum` introduced in
CPython 3.12 and keeps its four seeded CSV outputs byte-identical to the
recorded Python 3.11 baseline on both supported versions.

## Verification layers

1. `python scripts/reproduce_all.py` recomputes the seven-row production
   evidence audit and the original deterministic checks without rerunning
   machine-specific timing by default.
2. `python scripts/verify_production_snapshot_live.py` optionally verifies the
   archival block, active set, seven members, threshold, creation receipt, and
   `KeyperSetAdded` event through a Gnosis RPC endpoint.
3. `python extended_experiments/reproduce_extended.py` reproduces the three
   added experiment groups independently.
4. `cd deployment && python scripts/verify_chiado_certificate.py` verifies the
   machine-readable Chiado execution certificate, its exact threshold-cover
   value, and SHA-256 source bindings without network access.
5. `cd deployment && npm ci && npm run verify` runs certificate, static,
   TypeScript, and Solidity/Hardhat checks.
6. With a reachable Chiado RPC endpoint,
   `npm run verify:chiado:live` independently checks the recorded public chain
   trail without requiring a private key.
7. `python scripts/verify_manifest.py` verifies the complete distributable file
   set against `MANIFEST.sha256`.

The Dune provenance file now provides the available public query links. The
original raw SQL was not present in the archived inputs, so that limitation
remains explicit rather than being reconstructed or guessed.
