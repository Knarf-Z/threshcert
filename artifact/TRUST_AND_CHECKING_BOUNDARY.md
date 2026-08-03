# Trust and checking boundary (v49)

The artifact deliberately separates fresh computation from preserved evidence
and from assumptions that no included program proves.

| Layer | What the artifact checks | What it does not establish |
|---|---|---|
| Finite-LTS checker | `verify_offline_v49.mjs` freshly rejects duplicate/raw-inexact JSON, validates every mandatory LTS field, type, exact amount, origin consistency, irreversible counted debit, hash-bound source reference, B1--B5 rule, and shortest successful path on the supplied finite graph. It runs 40 schema, eight raw-JSON, four semantic, four rational, and three exact-boundary regressions plus 1,024 fixed-graph monotonicity comparisons. | It does not synthesize entries, callbacks, proxy or upgrade paths from bytecode. It does not discover leak, coercion, theft, common-control, reimbursement, or other off-chain routes. Deployment-wide use requires a separate route-completeness/refinement proof. |
| Fresh implementation rebuild | `verify_rebuild_v49.mjs` recompiles the pinned Solidity sources, runs 11 Hardhat tests, regenerates deployment admission, and invokes Halmos 0.3.3/Yices on all 82 named obligations with the recorded loop configuration. | Empty per-proof `bounds` fields do not mean quantification over arbitrary unknown callee bytecode or proof of the full EVM. The suite covers the pinned harness and two concrete hostile-receiver bases. |
| Integrity mode | `verify_integrity_v49.mjs` checks hashes, manifests, canonical JSON, semantic fields, and the preserved Halmos certificate/transcript. | It does not invoke Halmos. A valid preserved certificate proves identity and internal consistency, not fresh symbolic execution. |
| Human/external assumptions | The paper states an EVM call/storage-isolation lemma, usable-delivery predicate, registry and signature correctness, beneficial-control and funding provenance, reimbursement closure, and off-contract route coverage as named assumptions or separately admitted evidence. | None of these assumptions becomes machine checked merely because the finite-LTS or Halmos checks pass. |

The public four-case records contain no B1--B5 proof objects. Their zero outputs
are therefore record-derived missing-evidence diagnostics, not routes inferred
from source code or bytecode and not empirical claims of insecurity or
prevalence. The positive fixture has five states and four transitions; the
near-pass has four states and three transitions. Both are constructed tests.
