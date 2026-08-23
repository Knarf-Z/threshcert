# RSP-V6 restricted-source semantics and soundness argument

## 1. Scope

RSP-V6 is a proof policy for the controlled two-host threshold-response
implementation. It is intentionally not a verifier for arbitrary Python. Its
accepted programs consist of the exact ptr_v3 module set, the run_two_host
driver, the exact operator import closure, the reviewed critical normal forms
whose AST digests are frozen in source_coverage_kernel.py, and support code
that satisfies the whole-program escape and rebinding rules.

The claim is source-scoped. It assumes documented CPython and standard-library
semantics and that loaded application bytes equal the separately checked
hashes. It does not claim operating-system, interpreter, native-runtime,
hardware, side-channel, physical, dealer-erasure, or off-language security.

## 2. Why the extractor is not trusted

extract_restricted_source_inventory.py emits every source file, AST,
definition, import, call, and attribute occurrence. The proof kernel does not
trust its status or completeness. It reparses every source file and checks
equality of the inventory file set with the live set, a live SHA-256 over every
source, a live SHA-256 over every attribute-free AST, and every proof premise
below directly against the reparsed AST. An omitted or altered node changes the
full AST digest even if the extractor omits a row.

## 3. Accepted syntax and rejection rules

Let a program be a finite mapping from declared module names to CPython ASTs.
RSP-V6 accepts only if all of the following hold.

### G1. Closed source set

The application module set and operator import closure are exactly the
declared sets. Star imports and privileged-name import aliases are rejected.

### G2. No semantic escape

The whole checked source set contains no dynamic execution, dynamic import,
reflection over attributes or globals, subprocess creation, multiprocessing
escape, native-library loading, or undeclared server constructor.

### G3. No privileged rebinding

The names create_partial, combine_partials, _partial_and_proof, and _send are
neither aliased nor assigned. Attribute stores with those tails are rejected.

### G4. Exact critical normal forms

Functions containing request entry, response emission, share use, partial
creation, response verification, reconstruction, commitment checking, buyer
guarding, runtime binding, and the physical runner must match their reviewed
AST digests. Comments and line numbers are irrelevant; semantic AST drift is
rejected. A new critical implementation requires a new reviewed normal form
and a new policy identity.

## 4. Trace model

Project a standard-Python execution to these application events:

- Entry(method, route, request)
- ReadShare(operator)
- MakePartial(operator, ciphertext, epoch)
- EmitHTTP(code, payload)
- Combine(ciphertext, responders)
- VerifyCommitment(candidate, commitment)
- BuyerGuard(actual, declared)
- Deliver(plaintext)

Internal arithmetic, JSON construction, logging of nonsecret hashes, and
ordinary control-flow steps are silent.

The source proof concerns four trace properties:

- every capability-bearing successful HTTP emission is preceded by the unique
  declared MakePartial;
- every threshold-share read occurs as the share argument of that producer,
  and the payload contains a partial and proof rather than the share;
- sensitive operator fields are written only by the constructor and every
  accepted response binds the fixed runtime-source digest;
- every Deliver follows threshold Combine, successful commitment verification,
  and the successful named-buyer guard.

## 5. Transfer rules

Write effects(s) for the ordered event traces of statement s after silent
steps are erased.

### R-SEQ

A statement sequence concatenates the traces of its executed members and
therefore preserves event order.

### R-BRANCH

An if statement takes one branch and prefixes that branch trace with its guard
fact. A rejected early-return branch cannot continue to a later success site.

### R-LOCAL-CALL

A call to a fixed local function substitutes that function's checked summary.
G1, G2, and G3 make name resolution closed for privileged operations. G4 fixes
calls inside every critical function.

### R-PARTIAL

The only create_partial call is in _partial_and_proof. Its share argument is
the only load of state.share. It emits ReadShare followed by MakePartial.

### R-HTTP

The only raw HTTP operations occur in Handler._send. The only
capability-bearing successful call is self._send with status 200 and payload in
do_POST. The payload partial_decryption field is exactly the value returned by
the unique _partial_and_proof call. Thus every capability-bearing EmitHTTP has
the R-PARTIAL event as producer.

### R-COMBINE

The only combine_partials call assigns an internal candidate_plaintext and is
structurally guarded by threshold_reached. The candidate is then checked
against the ciphertext commitment.

### R-DELIVER

The deliverable plaintext starts empty. Its only nonempty assignment copies
candidate_plaintext inside the exact gateway_accepted branch. That guard is
the conjunction of successful aggregate verification and equality between the
actual consumer and ciphertext buyer. The same branch marks ledger success.

### R-REJECT

Any program violating a rule premise, closure rule, or critical normal form
has no RSP-V6 derivation and is rejected. No default positive conclusion is
produced.

## 6. Lemmas

### Lemma 1: privileged-site exhaustiveness

If G1 through G4 hold, every application-level partial creation, raw HTTP
emission, threshold reconstruction, and deliverable assignment corresponds to
one enumerated AST site.

Proof. Under standard Python source semantics these effects require a resolved
call or assignment. G1 closes modules; G2 removes dynamic execution, loading,
reflection, process and native escape, and extra listeners; G3 removes aliases
and rebinding; G4 fixes every remaining privileged operation. Structural
induction over statements and R-LOCAL-CALL leaves exactly the enumerated sites.

### Lemma 2: response-producer confinement

Every capability-bearing successful HTTP payload is derived from the unique
partial producer, and every threshold-share read is an argument of it.

Proof. Lemma 1 reduces emissions and reads to checked sites. R-PARTIAL gives
the unique read and producer. R-HTTP fixes the successful payload dataflow and
excludes secret fields. R-SEQ preserves producer-before-emission order.

### Lemma 3: guarded delivery

Every deliverable plaintext follows threshold reconstruction, commitment
verification, and the named-buyer guard.

Proof. Lemma 1 reduces reconstruction and delivery to the checked run_order
sites. R-COMBINE places candidate construction under threshold_reached.
R-DELIVER makes the only nonempty deliverable assignment occur under the exact
gateway conjunction. R-BRANCH and R-SEQ preserve guards and order.

### Lemma 4: source lifecycle closure

The threshold share, public share, and signing identity are assigned only
during OperatorState construction; accepted health and response records carry
the runtime digest of the exact operator closure; and the coordinator rejects
a mismatching digest.

Proof. G4 fixes constructor, signing, response, coordinator, and runner normal
forms. The exhaustive attribute-store check finds exactly the three constructor
stores. G2 and G3 exclude reflective or aliased replacement. The signing and
verification normal forms bind and compare the same digest.

## 7. Restricted-source-kernel soundness theorem

**Theorem.** Let S be accepted by the RSP-V6 kernel, let loaded application
bytes equal the source hashes in its certificate, and assume documented
CPython and imported standard-library semantics. Then every execution in the
declared RSP-V6 service language satisfies the source-level parts of LC1, LC3,
LC5, and LC7.

Proof. Lemma 2 gives source-level producer completeness and secret confinement,
which are LC1 and LC3 for the declared output and secret sources. Lemma 4 gives
fixed source lifecycle and signed runtime binding, the source-level LC5
obligation. Lemma 3 identifies the first event populating the only deliverable
plaintext field and proves its threshold, commitment, and buyer-guard root,
the source-level LC7 obligation. The lemmas hold for every accepted trace by
induction over R-SEQ, R-BRANCH, and R-LOCAL-CALL.

## 8. Independent representation check

compiler_bytecode_crosscheck.py asks CPython's compiler, without executing the
modules, for recursive code objects and instructions. It independently checks
the placement of the partial primitive, HTTP sinks, threshold reconstruction,
listener, and sensitive attribute stores. This is a cross-representation
validation axis, not a substitute for the theorem and not a third-party proof.

## 9. Role of mutations

The mutation matrix is a regression suite. It shows that the implementation
rejects listed edits; it is not evidence that the kernel is sound. Soundness is
supplied by the accepted-language definition, transfer rules, lemmas, and
theorem above.
