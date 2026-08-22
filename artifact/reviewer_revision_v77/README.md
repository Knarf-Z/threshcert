# C6/B5 completeness certificate (v77)

This directory contains the machine-readable completeness certificate requested by the paper review. It contains experiment code and results only; no manuscript source or PDF is included.

Run from the repository root:

```powershell
py -3.11 artifact\reviewer_revision_v77\verify_completeness_certificates_v1.py --output reviewer_revision_v77\results\completeness_certificates.v1.json --verify
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
py -3.11 artifact\reviewer_revision_v77\test_completeness_negative_controls_v1.py --root artifact --output reviewer_revision_v77\results\completeness_negative_controls.v15.json --verify
```

They accept a `buildInfoId`-only metadata drift and reject a semantic ABI route
addition, a removed reachable C6 path, a forged cheap success, a route-cost
change without runtime evidence, a bounded reverse proof, and an attempted
global-B5 escalation (7/7). `--verify` compares deterministic regeneration with
the committed v15 result instead of rewriting it.

The v15 experiment-only integration also checks:

- `artifact/finite_toy_delivery_extension`: explicit `Finalize` and `Deliver`,
  10 states, 11 transitions, two first-success routes, and 4/4 mutations;
- `artifact/process_route_stress_fixture`: three OPE-anchored process routes,
  contract costs `(4,4,4)`, net costs `(4,3,0)`, 5/5 route exclusions, and
  3/3 process-certificate mutations.

From the repository root, `python reproduce_v15_experiments.py` verifies these
extensions together with the frozen v77 C6 certificate and both manifests.

The scope distinction is intentional. The certificate proves C6 and route closure only for the admitted direct `OverlappingPoolEscrow` runtime. It does not exclude off-contract delivery, reimbursement, silent leakage, beneficial-control completions, or alternate deployments, so it cannot be used as a global named-acquirer payment certificate.