# C6/B5 completeness certificate (v76)

This directory contains the machine-readable completeness certificate requested by the paper review. It contains experiment code and results only; no manuscript source or PDF is included.

Run from the repository root:

```powershell
py -3.11 artifact\reviewer_revision_v76\verify_completeness_certificates_v1.py --output reviewer_revision_v76\results\completeness_certificates.v1.json --verify
```

The checker deterministically regenerates all 4,095 admitted root/terminal records and compares them byte-for-byte with the committed certificate. It also validates the pinned contract, compiled artifact, Halmos result and transcript, deployment-admission certificate, ten negative admission cases, and the refinement obligation map.

Expected result:

- `C6_CERTIFICATE=PASS`
- `C6_PATHS=4095_OF_4095`
- `B5_CONTRACT_LOCAL=PASS`
- `B5_DEPLOYMENT_GLOBAL=OPEN`
- `GLOBAL_PAYMENT_VERDICT=UNKNOWN`

Run the negative controls:

```powershell
py -3.11 artifact\reviewer_revision_v76\test_completeness_negative_controls_v1.py
```

They accept a `buildInfoId`-only metadata drift and reject a semantic ABI route addition, a missing C6 path, a bounded reverse proof, and an attempted global-B5 escalation (5/5).

The scope distinction is intentional. The certificate proves C6 and route closure only for the admitted direct `OverlappingPoolEscrow` runtime. It does not exclude off-contract delivery, reimbursement, silent leakage, beneficial-control completions, or alternate deployments, so it cannot be used as a global named-acquirer payment certificate.