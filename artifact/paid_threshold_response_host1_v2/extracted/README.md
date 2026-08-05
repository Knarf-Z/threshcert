# Paid Threshold Response — Host 1 positive certificate (v2)

A controlled single-host experiment that instantiates the paid-response model of
the paper with real threshold cryptography and emits a certificate that is
*derived from the execution ledger* rather than substituted from the closed-form
cover value.

## What it computes

Four quantities, four separate code paths:

| Quantity | Where it comes from |
| --- | --- |
| `theory_cover` | `certificate.theory_cover`: the sum of the `q` smallest declared floors. Never consults an execution. |
| `execution_floor(h)` | `evidence.evaluate_execution`: `Σ_{i∈Q_c(h)} (D_i − R_i − F_i)` from that execution's allocation witness. |
| `catalog_certificate` | `certificate.catalog_certificate`: the minimum of the ledger-derived floors over the enumerated route catalog. |
| `observed_minimum` | the minimum realized named-buyer net outflow over the same catalog. |

With floors `(1,2,3,4,5,6,7)` and `q = 4` all four equal `10`, and the coalition
`{4,5,6,7}` reports `execution_floor = 22`. Nothing in the code makes the four
agree by construction.

## Proof objects

- `aggregation_witness` names `Q_c(h)` — operator ids, partial-response hashes,
  order, buyer, resource, epoch, responder bitmap.
- `allocation_witness` instantiates (C2) over the same bitmap: unique debit
  identifiers, no double-allocated refund or funding identifier, `D_i − R_i − F_i
  ≥ p_i` per counted responder, and a total within the realized outflow.
- `route_coverage_evidence` replaces the old boolean flag with a three-status
  object (`PROVED`, `REFUTED` with a bypass trace, `UNKNOWN`).
- `c1_non_exportability_witness` records the operator interface, the absence of
  an export operation, and the module source hashes, scoped to the declared
  finite service language.
- `c3_minimum_cover_witness` records the cheapest coalition, its ledger-derived
  floor, and that the declared floors are attained exactly.

## Verdicts

Gates return `PASS`, `FAIL_COUNTEREXAMPLE`, `FAIL_CLOSED_MISSING_EVIDENCE` or
`NOT_APPLICABLE`; the report is `CERTIFIED`, `REFUTED` or `UNKNOWN`. Missing
evidence never reads as a refutation.

## Running

See `HOST1_QUICKSTART.txt`. Scope boundaries are in `PAPER_CLAIMS.md`; the v1
result is preserved unmodified in `legacy/host1_result.v1.json`.
