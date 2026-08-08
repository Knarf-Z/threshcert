# Controlled two-host threshold-response evidence (V5)

This module publishes the final public evidence from a controlled 4-of-7
threshold-ElGamal experiment executed across two physical Windows hosts. It
certifies the named acquirer's exact net outflow inside the declared finite
service language. It does not claim deployment-wide route closure, seven
independent economic operators, hardware non-exportability, operating-system
integrity, or a measured bribery price.

The retained `ptr_v3` Python namespace and `*.v3.json` filenames are
compatibility names. The protocol and result schemas inside the frozen
packages are V5.

## Frozen packages

```text
frozen/two_host_execution_evidence.public.zip
frozen/code_fidelity_evidence.zip
verify_two_host_v5.mjs
```

Pinned identities:

```text
execution evidence SHA-256  f3be587c4586a193ba1f2515f7f5c612b11162e80b42253bc30496976f25e65e
code fidelity SHA-256       8b5dff61e3cde30402eeda19869626d721b6910135afa5221dba91dade95f71e
code manifest identity      b1a84b542b752e4686f164aecf856167ffe5391fb778267d0cff0a5e551ad468
canonical result SHA-256    4000b777402fe4d2435287c69a4eb6c7c6e2cc84df64088162750ddcc7f22478
source-kernel result        6f1327541769d77f2a60d7c331c933682879a50912cbb457f8ef9d640d82406c
end-to-end result           58950527a202d0bf55324b05e7803073f063e0df25daa346d45acbf1283396c9
```

## Checked claims

The standalone Node verifier checks both outer package digests, each public
archive manifest entry, the privacy boundary, the archived code-manifest
bindings, and the result-to-result hash chain. It then checks:

- real threshold delivery with four responses from a seven-member committee
  split across two observed hosts;
- complete enumeration of all 840 ordered four-responder routes, including 24
  minimizing routes;
- theory cover, ledger-derived catalog certificate, observed minimum, verified
  lower bound, and realized exact value all equal 10;
- source obligations LC1, LC3, LC5, and LC7 pass, and all 14 source mutations
  are caught;
- the sealed component contract passes and each LC0-LC7 mutation is caught;
- a feasible payment potential proves the lower bound, a free bypass refutes
  it, and a shared debit is rejected as nondecomposable;
- code-to-manifest fidelity passes and all six code-surface mutations are
  caught;
- outage fails closed, recovery succeeds, and both are bound to the final code
  manifest and canonical result.

Run from this directory:

```text
node verify_two_host_v5.mjs
```

For a second, Python-based verification using the verifier embedded in the
public archive, extract the archive and run:

```text
py -3.11 project/scripts/export_public_release.py --verify-only two_host_execution_evidence.public.zip
```

No secret share, real topology address, nonce log, cache, backup, or private
Host 2 package is included here.