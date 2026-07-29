# Pinned Gnosis production snapshot

This directory separates two checks:

1. `python verify_offline.py` recomputes the public-evidence certificate from
   the fixed snapshot record and evidence ledger, compares both canonical
   result files, and performs no network access or writes.
2. `python scripts/verify_production_snapshot_live.py --rpc <archive-rpc-url>`
   rechecks the pinned block, manager calls, active Keyper set, members,
   threshold, owner/publisher/finalization state, creation receipt, and
   `KeyperSetAdded` event using a user-supplied read-only Gnosis archive RPC.

The pinned observation is chain ID 100, block 46,666,718, active set index 10,
and a finalized four-of-seven committee. The evidence ledger contains no
period- and scope-matched positive resistance, activation, forfeiture,
insurance, or compensation floor. Therefore the certified public lower bound
is zero. `UNKNOWN_NOT_MEASURED` is retained separately for actual member
resistance; the artifact does not interpret missing evidence as zero economic
cost.

`python scripts/run_production_evidence_audit.py` regenerates the two result
files from `data/`. The root `node verify_all.mjs` uses the non-mutating offline
checker and never contacts a chain.