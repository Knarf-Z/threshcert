# Canonical V6.2 public artifact

This directory publishes the single formal artifact entry point for the V6.2
paper. It combines the frozen two-host V6 execution evidence, the RSP-V6.2
control/effect/simulation supplement, and the pinned external NuCypher source
audit in one deterministic archive.

Run from the repository root with CPython 3.11 and Node.js:

```text
py -3.11 -B artifact/paid_threshold_response_two_host_v6_2_canonical/verify_canonical_archive.py
```

The wrapper verifies the exact archive identity, extracts it to a temporary
directory, and invokes its single top-level verifier. Inside the archive there
is exactly one `MANIFEST.sha256`, covering every other extracted file. Expected
final line:

```text
TWO_HOST_V6_2_CANONICAL_ARCHIVE=PASS
```

The application and wire-protocol bytes are unchanged from V6.2's frozen V6
execution payload, so no new physical Host 2 run is required.
