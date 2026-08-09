# Two-host V6.2 canonical public release

This archive has one manifest and one top-level command:

```text
py -3.11 -B verify_canonical_release.py
```

`MANIFEST.sha256` covers every other extracted file. The top-level verifier
then runs three byte-bound checks:

1. the frozen V6 two-host execution and code-fidelity verifier;
2. the RSP-V6.2 control profile, complete effect-site closure, request-indexed
   sound-simulation supplement, and bounded differential validation; and
3. the pinned NuCypher v7.6.1 external source audit, whose expected fail-closed
   result is `UNKNOWN` for all four source obligations.

An `UNKNOWN` external audit is not a vulnerability report or a positive
certificate. It records that independently maintained real-world code crosses
framework, native, concurrency, and lifecycle boundaries outside the accepted
restricted source model.

Prerequisites are CPython 3.11 and Node.js. The verifier performs no network
access and does not contain private Host 2 material.
