# Closed-contract incidence versus production economic incidence

The overlapping-pool component proves a fixture-specific, closed-contract
settlement property for one admitted Cancun runtime. It now discharges more
than a call-value counter:

1. **Controller-funded offsets.** The controller is distinct from every member
   and is the only caller permitted to configure credits. Configuration succeeds
   only when `msg.value` equals the immutable credit total. The contract has no
   controller refund path.
2. **Role-separated payer.** A successful acquisition caller must be neither
   controller nor member, supplies exactly the residual payment, and has no
   claimable balance, rebate, refund, or withdrawal path in the contract.
3. **Controlled delivery.** Before acquisition each of seven unique on-chain
   share rights belongs to its corresponding member. The unique successful
   `acquireFour` transition transfers exactly the selected four rights to the
   payer and sets `deliveredShareMask = terminalMask`.

These properties are covered by deployment admission, source-order/value-flow
checks, 82 Halmos obligations with empty bounds, and independent finite-schema
verification. Consequently the minimum **closed-contract controlled-share-right
incidence** is four units for the admitted fixture. This positive value no
longer depends on unproved contract-internal funding or delivery premises.

The formal lifting is equally scoped. The abstract terminal family is exactly
the 35 four-subsets, and the closed-contract outcome semantics is exactly the
set of successful admitted EVM traces, including their payment labels. Thus
terminal-family completeness and trace--outcome correspondence hold here. They
do not identify those traces with an external willingness, bargaining, or
production-decryption outcome system.

The certificate deliberately does not turn Ethereum addresses or share-right
labels into facts about the outside world. It does not establish:

- that nominally distinct controller, member, and payer addresses lack common
  beneficial control;
- that the payer receives no off-contract reimbursement, hedge, indemnity, or
  side transfer;
- that a controlled share right contains a confidential and cryptographically
  usable premature threshold-decryption share;
- that members are willing to participate or that production Shutter implements
  this fixture.

A production economic-incidence claim therefore still requires scope-matched
evidence for two external bindings:

1. **Cryptographic binding:** each controlled right is bound to delivery of a
   usable premature share for the production threshold instance.
2. **External identity/value binding:** role-separated addresses are also
   independent at the beneficial-control level and the payer remains net-funded
   after every in-scope off-contract transfer.

Without those bindings, the fail-closed output is the positive controlled-
runtime incidence result plus a zero public-evidence production certificate;
no positive production-Shutter incidence follows.
