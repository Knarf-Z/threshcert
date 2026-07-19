# Security boundary

This artifact never needs a mainnet key. Use newly generated, Chiado-only accounts.

- `CHIADO_DEPLOYER_PRIVATE_KEY` sends deployment, registration, job, and slashing transactions.
- `EVIDENCE_VERIFIER_PRIVATE_KEY` signs only EIP-712 evidence attestations and must be a different key.
- Neither key is written to JSON output, source files, command-line flags, or the manifest.
- Runtime Rolling Shutter Keyper keys are freshly generated under the ignored upstream checkout.
- The well-known Anvil key in the local Docker scripts controls only the disposable local execution chain.

The Solidity contract does not verify Shutter BLS12-381 proofs directly. The pinned Go verifier checks
the BLS share, native Keyper signature, aggregate key, and threshold reconstruction off chain. The
contract verifies that verifier's EIP-712 attestation, enforces the release deadline, transfers the
bond, and updates the certificate. Paper claims must describe this as **verifier-gated slashing**.

The machine-readable Chiado certificate is a positive certificate only for the
recorded controlled testnet mechanism. It certifies the observed on-chain bond
floor and evidence-to-enforcement execution. It does not certify production
Keyper resistance, activation thresholds, operator independence, or a
deployment-wide lower bound on detection and enforcement probability.
