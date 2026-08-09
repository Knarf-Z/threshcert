# External threshold-service source audit v1

This artifact applies the paper's source-obligation audit to a pinned,
independently authored open-source snapshot of the NuCypher Threshold Access
Control node runtime at release `v7.6.1`, published 2025-09-24, and commit
`547a9646d929f5f035b054bef94720c5712448c5`. At retrieval, the official
repository marked the project inactive and no longer maintained.

The result is deliberately fail-closed: `LC1`, `LC3`, `LC5`, and `LC7` are all
`UNKNOWN`. The selected Python source confirms the decryption route and share
production chain, but a positive RSP certificate is unavailable because the
event-relevant slice crosses Flask decorators and callbacks, a native DKG
boundary carrying the private key, worker-pool concurrency, and lifecycle
state outside the closed restricted language.

`UNKNOWN` is neither a violation finding nor a claim that NuCypher is insecure.
It demonstrates that the audit can be run on independently authored code and
does not turn an unclosed source model into a positive certificate.

## Reproduction

From the repository root, with CPython 3.11:

Windows:

```text
py -3.11 -B artifact/external_threshold_service_audit_v1/verify_external_audit.py
```

Linux/macOS:

```text
python3.11 -B artifact/external_threshold_service_audit_v1/verify_external_audit.py
```

Expected final lines include:

```text
EXTERNAL_THRESHOLD_SERVICE_AUDIT=UNKNOWN
EXTERNAL_AUDIT_VERIFICATION=PASS
```

The verifier checks `MANIFEST.sha256`, reparses the pinned selected-source
snapshot, recomputes the structural facts, and byte-compares the result with
the frozen audit JSON. The full upstream repository and release remain
available at the official URLs in `UPSTREAM.json`.

## Scope and licensing

Only files needed to reproduce the source-boundary result are redistributed.
The upstream `LICENSE` is included in the selected-source archive and copied as
`LICENSE.AGPL-3.0`. NuCypher remains copyright its respective contributors and
is licensed under the GNU Affero General Public License, version 3.
