# Admitted-runtime EVM-to-schema refinement proof

This directory contains the Halmos harness for the pinned
`OverlappingPoolEscrow` fixture. It proves the restricted claim

```text
Init(y) for every admissible y;
T_OPE,postcfg^EVM <=_pi T_OPE^sch
```

for an exact non-proxy Cancun runtime admitted against a successful direct
creation transaction and its constructor arguments. The controller is fixed
and role-separated from seven distinct nonzero members. Member addresses need not be code-empty. Arbitrary-callee closure relies on
the admitted Cancun runtime's sole locked `CALL` plus EVM caller-storage
isolation; the two concrete hostile receivers machine-check the complete
mutating-reentry basis, but Halmos does not quantify over unknown callee
bytecode. Delegation-style code on later revisions requires a separately
revision-matched admission record.

The admitted fresh deployment is outside the refined acquisition LTS. A
symbolic initialization obligation proves that each admissible `y` yields one
root with `configured=true`, `credits=y`, `claimable[member_i]=y_i`, escrow
balance `sum(y)`, `shareOwner[i]=member_i`, zero terminal/delivery masks, a
zero acquisition-call-value counter, and a zero acquirer. On the resulting
post-configuration LTS the projection is

```text
pi = (credits, completed, terminalMask, deliveredShareMask,
      totalAcquisitionCallValue).
```

`configured` is fixed true. `acquirer` and `shareOwner` are auxiliary
invariants: at a root the acquirer is zero and every share right belongs to its
member; after the unique successful acquisition, the acquirer is the exact
external payer and exactly the selected four share rights belong to it. Replay
and withdrawal preserve these fields. `claimable` accounting and successful or
reverting withdrawals are projection-neutral.

The proof covers every subsequent top-level `acquireFour` and `withdraw` call.
Configuration and acquisition values range over the full `uint256` domain;
withdrawal is nonpayable. Reverting calls are projected stutters, not abstract
edges. Views are observations outside the transition LTS.

## What is machine proved

- 35 canonical `acquireFour` wrappers, one for every increasing four-subset;
  all seven credit coordinates, every wrong payment over the full `uint256`
  domain, and the payer address stay symbolic. The payer is assumed nonzero and
  distinct from the controller, all members, the proof VM, and the escrow;
  exact payment must succeed, bind `acquirer`, receive all four selected
  rights, and retain zero `claimable` balance.
- Exact quote/call-value closure, payer binding, the four-unit residual lower
  bound, terminal/delivery-mask preservation, selected/unselected share-right
  ownership, and backward realization for every abstract terminal.
- Controller/member constructor separation plus eight role-conflict wrappers:
  the controller and each of seven members are rejected as acquisition payer
  for symbolic admissible credit vectors.
- One-time configuration and completion, including arbitrary failed
  reconfiguration and arbitrary completed-state acquisition replay.
- Nine general auxiliary closure proofs: bidirectional configuration success,
  excess funding/candidates, oversize credit/value, unauthorized configuration,
  unknown selectors/value, every non-canonical tuple/value, completed replay,
  reconfiguration, and nonpayable withdrawal value rejection.
- Seven pre-terminal withdrawal obligations and 21 terminal obligations
  covering, for every member, selected, selected-after-pool-withdrawal, and
  unselected claimable classes. Successful and reverting withdrawals preserve
  the projection and share-right invariants.
- Two hostile-member callback obligations before and after completion. The
  receiver calls every mutating entry during withdrawal; the shared lock rejects
  every callback and preserves the projection.

The machine-readable `../results/refinement_obligation_map.json` connects every
refinement clause to these proofs, source-level fiber and value-flow checks,
deployment admission, and finite-schema checks, and lists the trusted computing
base. The preserved suite contains 82 obligations. Every accepted proof line
must report `bounds: []`. The runner rejects a counterexample, timeout or
truncation marker, nonzero failure count, missing or unexpected proof, or
nonempty exploration bound.

## Reproduce

Prerequisites are Python 3.10+, Foundry/Forge 1.7.1, Solidity 0.8.28, and the
packages pinned in `requirements.txt`. From `joint_incidence_refinement/`:

```text
python -m pip install -r formal/requirements.txt
python scripts/run_halmos_bridge.py --jobs 4 --loop 8 --solver yices-2.6.4
```

The run writes `results/halmos_evm_bridge.log` and
`results/halmos_evm_bridge.json`. It is CPU intensive and took about 24
minutes on the authors' four-job Windows run.

On Windows, if the transitive `safe-pysha3` package cannot build, install
Halmos 0.3.3 without dependencies, install its declared dependencies plus
`pycryptodome`, and set `ETH_HASH_BACKEND=pycryptodome`. This workaround does
not change the Solidity bytecode or proof obligations.

## Explicit exclusions

This is not a theorem about arbitrary contracts or production Shutter. It
excludes a runtime-template mismatch, an uncertified creation transaction,
proxies, upgrades, `delegatecall`, `CREATE`, `CREATE2`, `selfdestruct`, gas
exhaustion, chain reorganization, and non-Cancun revisions. Arbitrary member
code is admitted only for the paper projection: the sole external `CALL` occurs
in withdrawal, every mutating entry shares the lock, and callback success or
failure is projection-neutral.

Within this admitted contract ledger, controller-funded credits, exact funding
by a controller/member-separated payer, lack of a payer refund/withdrawal path,
and transfer of four controlled share rights are proved. The certificate does
not prove off-contract reimbursement closure or distinct beneficial ownership,
cryptographic usability/confidentiality of a share right, member willingness,
production pass-through, or a nonzero production incidence value.
