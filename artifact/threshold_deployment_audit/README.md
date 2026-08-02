# Preregistered threshold-deployment bridge audit

This directory contains a fixed-cohort audit of whether public records can
certify attacker-funded acquisition payment. The cohort and checklist were
committed before the per-system results were generated. The audit is a
purposive, cross-application stress cohort, not a random sample and not a
prevalence estimate.

The frozen inputs are:

- `cohort.v1.json`: four public threshold deployments and their selection rule;
- `policy.bridge-evidence.v1.json`: claim semantics, five bridge gates,
  loss-floor fields, temporal fields, and fail-closed decision rules.

Later result records must not change these files. A system passes a positive
attacker-payment claim only when all five bridge gates are supported for the
same deployment, event, time interval, payer, usable-delivery predicate, and
mechanism language. Threshold-only, slashing-only, and self-reported-price
baselines are evaluated separately. Missing evidence produces zero, not a
claim that the system is insecure or that real acquisition would be free.

The audit cutoff is `2026-08-03T02:21:32+08:00`.

