# Controlled paid threshold-response positive certificate (v2)

The only module in this artifact that produces a *positive* payment certificate
from real threshold cryptography. Everything else in the artifact either audits
public records to zero or exercises the accounting layer with a mock verifier.

## Layout

```text
frozen/ptr_host1_v2.zip      the frozen archive; never modified
extracted/                   byte-identical expansion of the frozen archive
verify_ptr_host1_v2.mjs      integrity, replay and claim verifier
```

Pinned identities:

```text
frozen ZIP SHA-256   f64ef30657cc64940155f2ec37808e72154dec76255172d6e11412e65b603415
canonical SHA-256    492ada8c05d24193fec4821d9038c851eab8861214145974a12b36b269bf8148
```

## What the verifier establishes

1. `frozen/ptr_host1_v2.zip` still hashes to the pinned digest.
2. `extracted/` is byte-identical to that archive, entry by entry, read out of
   the zip's own central directory rather than by re-running an unzip tool.
3. `results/canonical_result.v2.json` carries the pinned canonical digest, and
   `results/run_metadata.v2.json` is absent from the nested manifest, so PIDs,
   timings and platform strings cannot move the canonical hash.
4. The experiment re-runs from `extracted/` and reproduces the canonical result
   byte for byte; the nested unit tests, result verifier and manifest verifier
   all pass.
5. Each number the manuscript quotes is asserted individually: 840 ordered
   routes, all floors ledger-derived, theory cover / catalog certificate /
   observed minimum / baseline execution floor all 10, 24 minimizing routes,
   `{4,5,6,7}` floored at 22, a diagonal ablation matrix, and the separation of
   `UNKNOWN` from `REFUTED`.

Point 5 exists so that a drift between the paper and this record fails in the
checker rather than in review.

## Scope

The certificate is positive *for the declared finite service language*. It is
not a deployment-wide claim. One physical Windows host; seven operator processes
of which four are counted responders; a trusted deterministic dealer; a seeded
non-cryptographic test RNG; no HSM, TEE or attestation. `extracted/PAPER_CLAIMS.md`
states the supported and unsupported claims in full.

The superseded v1 run is preserved at `extracted/legacy/host1_result.v1.json`.
It is not used by the default reproduction: its reported certificate was the
uniform closed form substituted on a gate pass, which is exactly what v2
replaces with a ledger-derived quantity.
