# Controlled two-host threshold-response evidence (v3 + v4 fidelity)

This module publishes the two public evidence packages from the controlled
4-of-7 threshold-ElGamal experiment run across two physical Windows hosts.
The certificate is scoped to the declared finite service language. It is not a
deployment-wide claim, evidence of seven independent economic operators, or a
hardware non-exportability result.

## Frozen packages

```text
frozen/two_host_execution_evidence.public.zip
frozen/code_fidelity_evidence.zip
verify_two_host_v4.mjs
```

Pinned public-package identities:

```text
execution evidence SHA-256  e91b8209867db8e366b7dc8a37cee64310fa998643fa3eb86d295209e59d5d37
code fidelity SHA-256       fdb62bcedf1a63aa672c34239f698844ac2be092a32e3e46d64118ed5a9aca9b
code manifest SHA-256       7d533f5ce311a01734608d4eaa2a8f44d77241c4425a5d0cf9c30949d0694871
```

The execution package is a deterministic public-release derivative of
`two_host_v3_combined_evidence_20260808_004756.zip`, whose SHA-256 is
`2703aee4335402037181a18e4f5afeefc3d99f5da2aeab35d0de9eb331dee98e`.
The original combined package and the outer V4 bundle are intentionally not
committed: their own `README_PACKAGE.txt` requires removing
`private_metadata/` before public release. The public derivative also omits the
nested Host 2 provenance ZIP because it contains the same private host
metadata, plus Python caches and patch backups. The original desktop archives
remain unchanged.

## Checked claims

The verifier checks both package digests, the public archive's internal
manifest and privacy boundary, and each manuscript-facing result:

- real 4-of-7 threshold cryptography split across two observed hosts;
- theory cover, ledger-derived execution floor, catalog certificate, and
  observed minimum all equal 10;
- all 840 ordered four-responder routes are represented, with 24 minimizers;
- the remote-only coalition floors at 19 and the expensive coalition at 22;
- outage and recovery checks pass;
- the payment-capability potential certifies 10, a free bypass refutes it, and
  a shared debit is rejected as nondecomposable;
- the sealed-composition baseline passes and every LC0-LC7 mutation is caught;
- code-to-manifest fidelity passes and all six code-surface mutations are
  caught.

Run from this directory:

```text
node verify_two_host_v4.mjs
```
