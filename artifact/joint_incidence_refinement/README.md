# EVM-to-schema refinement artifact

This component certifies the constructed `OverlappingPoolEscrow` example in
three separately checkable layers.

1. **Deployment admission.** A record binds a successful direct creation
   transaction, constructor arguments, the exact runtime template modulo the
   controller immutable, controller/member role separation, initial member-owned
   share rights, the ABI entry set, and opcode guards.
2. **Initialization plus implementation refinement.** A symbolic configuration
   obligation proves that every admissible credit vector initializes one exact
   post-configuration root, including controller-funded credits, claimable
   balances, escrow balance, initial share-right ownership, zero delivery/payment
   masks, and a zero acquirer. Halmos/Yices then proves 82 obligations: 35
   symbolic acquisition wrappers with a full-domain role-separated payer, 28 withdrawal-fiber wrappers, nine general
   closure obligations, eight role-conflict obligations, and two hostile-member
   callback obligations. Every accepted proof has `bounds: []`.
3. **Finite schema and lifting boundary.** Independent Node and Python checkers enumerate all
   117 admissible credit vectors and exactly the 35 declared terminal sets, verify all 4,095 edges,
   backward realization, terminal equivalence, payment preservation, and terminal-family completeness.
   For the closed-contract mechanism only, outcomes are defined as successful admitted EVM traces,
   which discharges payment-labelled trace--outcome correspondence; no external-profile lift is claimed.

`results/refinement_obligation_map.json` maps initialization, offset-lift structure, terminal-family completeness,
closed-contract trace--outcome correspondence, entry closure, forward simulation,
backward realization, terminal equivalence, payment preservation, closed-contract economic incidence, and callback/fiber closure
to concrete evidence and states the trusted computing base. The deployment
admission layer removes a prose-only fresh-fixture premise. Member addresses are not required to be code-empty. This closure has two
explicit layers: the admitted Cancun runtime has one external `CALL`, no
`DELEGATECALL`/`CALLCODE`, and a lock held across withdrawal, so the EVM
call/storage-isolation argument reduces arbitrary callee behavior to return,
revert, or mutating reentry; two concrete hostile receivers machine-check the
complete mutating-reentry basis in root and terminal fibers. Halmos does not
quantify over unknown callee bytecode. Delegation-style code on later EVM
revisions needs a revision-matched admission record.

Within the admitted contract ledger, the controller is distinct from all
members and is the only exact funder of the fixed credit vector. A successful
acquirer must be neither controller nor member, supplies the exact residual
call value, receives exactly the four selected on-chain share rights, and has
no claimable balance, refund, rebate, or withdrawal path. Thus the controlled
share-right incidence value of four is machine discharged rather than assumed.

A second, deliberately narrower construction, `PrefundedThresholdExchange`,
tests the payment bridge directly: a named buyer prefunds an immutable order,
registered members submit verifier-approved shares, credits become withdrawable
only after the registered threshold set is complete, and the contract has no
cancel, refund, upgrade, delegate-call, or fallback entry. The certificate and
offline checker preserve the source/runtime hashes and five focused tests.
This closed-contract claim is not an oracle for off-contract beneficial
ownership or reimbursement. It does not prove that a controlled share right
contains a confidential, cryptographically usable premature decryption share,
that nominally distinct addresses lack common control or side transfers, that
members are willing to participate, or that the construction passes through to
production Shutter. No nonzero production-Shutter certificate is claimed.

## Offline verification

After `npm ci` and `npm run compile` have produced the pinned artifact:

```text
npm test
npm run admission:verify
npm run admission:negative
npm run refinement:check
npm run prefunded:verify
python verify_schema_independent.py
```

The preserved Halmos run can be reproduced with:

```text
python scripts/run_halmos_bridge.py --jobs 4 --loop 8 --solver yices-2.6.4
```

## Archive-RPC admission for another direct deployment

The capture command requires the deployment to be the final transaction in its
block so that block-end calls are the constructor post-state:

```text
node scripts/capture_deployment_admission.mjs --rpc ARCHIVE_RPC_URL --tx 0xDEPLOYMENT_TX --out results/deployment_admission_public.json
```

The checker is fail-closed: runtime-template, constructor/role, receipt/block,
initial share-right state, ABI, or opcode mismatch rejects admission. The
public record must be independently retained with its source and result hashes.
