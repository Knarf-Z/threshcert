# RSP-V6.1 concrete-to-trace soundness supplement

## 1. The object proved

Let `S_cert` be the exact source-byte mapping archived in
`two_host_v6_final_evidence_20260809.zip`.  The supplement verifies the outer
archive digest, reparses those bytes, checks every source byte string against
the archived code manifest, and derives semantic predicates from the resulting
AST.  The theorem below is first a theorem about `S_cert`, not about a hash.

For a deployed run, the theorem applies under the explicit premise

```text
S_loaded is byte-identical to S_cert.
```

The signed runtime record tests equality of their SHA-256 digests.  Inferring
byte identity from that test additionally assumes collision resistance and a
correct runtime measurement path.  A byte string does not “equal its hash.”

AST digests are also identity commitments only.  They reject unreviewed drift;
they do not establish a semantic summary.  Every semantic premise used below
is recomputed by `verify_control_profile.py` as a structural predicate over the
certified AST.

## 2. Concrete and abstract semantics

A concrete per-request CPython state is a tuple of the current source
statement, local and object stores, exception or return continuation, lock
state, and the finite request/response environment.  We use the documented
Python 3.11 semantics for expression evaluation, calls, `if`, `for`, `return`,
`try`, and `with`, together with the documented `BaseHTTPRequestHandler`,
`ThreadingHTTPServer`, and `threading.Lock` contracts.

The projection `alpha` erases ordinary computation and retains only:

```text
request-entry
share-read
partial-create
http-emit
threshold-combine
commitment-verify
buyer-guard
usable-deliver
```

`Trace_RSP(S, i)` is the set of traces produced by the rules in Section 4 for
source `S` and admitted input `i`.  It is a set because request order, guard
outcomes, transport failure, and thread interleaving may vary.  The target is

```text
alpha(Exec_CPython_3_11(S, i)) is a subset of Trace_RSP_V6_1(S, alpha(i)).
```

This is a safety simulation.  It does not assert termination.  A concrete
execution that blocks or raises before a successful response contributes only
its projected prefix.

## 3. Accepted control profile

RSP-V6.1 accepts the following forms in the event-relevant slice:

- simple expressions, assignments, and data construction whose callees are
  closed and classified;
- statement sequences and `if` branches;
- `for` and comprehension iteration over a materialized finite list, tuple,
  range, or the declared response sequence;
- `return`, which cuts off the remaining statements in its current function;
- exactly two caught-exception profiles: malformed JSON maps to an HTTP 400
  followed by return, and declared transport exceptions map to a rejected
  response followed by return;
- `with` on the declared standard-library file/socket handles or on the single
  operator lock; acquisition of the same non-reentrant lock may not nest;
- fixed local calls whose event-relevant call graph is inlined structurally;
- the single `ThreadingHTTPServer` callback surface with exactly `do_GET` and
  `do_POST`, and the single thread target `server.serve_forever`;
- the built-in `dataclass`, `staticmethod`, `classmethod`, and `property`
  descriptors.  No user-defined descriptor hook exists in the operator
  closure.

The only `while` in the cryptographic event slice is the scalar rejection
sampler.  It is event-silent until it returns; nontermination therefore cannot
create a forbidden successful event.  Other lifecycle and bitmap loops are
outside the event-relevant slice and are checked to contain no privileged site.

RSP-V6.1 rejects, in the event-relevant slice:

- `async`, `await`, asynchronous iteration/context managers, generators, and
  `yield`;
- dynamic execution/import, reflection over capability-bearing state,
  subprocess/native escape, wildcard import, or privileged-name rebinding;
- dynamic callback registration, an additional listener, or an additional raw
  HTTP sink;
- a user-defined decorator, descriptor hook, metaclass, or context manager;
- a broad or bare exception handler that can fall through to success;
- an unclassified loop iterator, nested acquisition of the same non-reentrant
  lock, or an unclassified library call with projected effects.

Generators, lambdas, and loops may occur in event-pure support functions only
when whole-program privileged-site exhaustiveness proves that they cannot
create a projected event.  This is an explicit two-slice rule, not an implicit
assumption that Python lacks those constructs.

## 4. Simulation rules

### R-SILENT

An accepted expression or assignment with no projected site takes concrete
steps whose `alpha` projection is empty.

### R-SEQ

If the left statement terminates normally, concatenate its abstract trace with
the right trace.  A return or exception continuation suppresses the unexecuted
suffix, exactly as in the concrete semantics.

### R-BRANCH

Evaluate the guard silently and simulate only the selected branch.  An early
return in a rejecting branch cannot fall through to a later success site.

### R-FOR

For a finite admitted iterator, unroll the body once per concrete element and
apply R-SEQ.  A return or exception stops the unrolling.  The scalar rejection
loop is treated as zero or more silent iterations followed by its return.

### R-TRY

Normal completion simulates the body.  The declared exception types transfer
control to their exact handlers; each handler produces a rejecting action and
returns.  Any other exception aborts the current request and cannot add a
successful emission or delivery event.

### R-WITH

Under the documented standard-library contract, `__enter__` and `__exit__` for
the allowlisted file/socket handles and `threading.Lock` add no projected
event.  The body is simulated recursively; cleanup also runs on return or
exception.  The non-nesting check excludes self-deadlock from the accepted
grammar.

### R-INLINE

A fixed local call is simulated by binding actual arguments to the certified
callee and applying the statement rules to its body.  The control-profile
checker closes event-relevant call targets and rejects aliasing, rebinding,
dynamic import, reflection, and user-defined descriptor hooks.  No arbitrary
“reviewed summary” is substituted.

### R-CALLBACK and R-THREAD

The documented HTTP dispatcher selects the declared `do_METHOD` handler.  The
certified handler class has no custom initializer and exactly the four reviewed
methods.  `ThreadingHTTPServer` may interleave per-request traces arbitrarily.
LC1, LC3, LC5, and LC7 are prefix-closed per-request safety properties, so an
interleaving preserves them.  The nonce check/update is linearized by the
allowlisted lock; the proof does not assume a deterministic thread schedule.

### R-PARTIAL and R-HTTP

The whole-program AST contains one `create_partial` call and one load of
`state.share`, both in `_partial_and_proof`.  Every raw HTTP sink is in `_send`.
The unique successful `do_POST` call sends the payload derived from that
producer; the payload contains the partial and proof but no share or plaintext.

### R-COMBINE and R-DELIVER

The sole `combine_partials` call writes `candidate_plaintext` under
`threshold_reached`.  The commitment predicate is evaluated on that candidate.
The only nonempty write to deliverable `plaintext` occurs under the conjunction
of successful commitment verification and exact buyer equality.  The same
branch marks ledger success.

## 5. Statement simulation lemma

**Lemma.** For each accepted event-relevant statement `s`, concrete state
`sigma`, and admitted input, every projected CPython execution prefix of `s`
is a prefix of a trace derived for `s` by RSP-V6.1.

**Proof.** By structural induction on `s`.

- Expressions and assignments use R-SILENT unless they are one of the directly
  classified event sites.
- Sequences, branches, finite loops, returns, exceptions, and context managers
  follow R-SEQ, R-BRANCH, R-FOR, R-TRY, and R-WITH respectively.
- Fixed calls use R-INLINE and the induction hypothesis on the callee body.
- Callback invocation uses R-CALLBACK; arbitrary scheduling uses R-THREAD and
  preserves each per-request projected order.
- At the four privileged families, the structural dataflow predicates give
  R-PARTIAL, R-HTTP, R-COMBINE, and R-DELIVER.

The rejected constructs in Section 3 are exactly the cases for which no rule is
provided.  Therefore no accepted concrete statement lacks a simulation case.

## 6. Application lemmas

**Producer lemma.** Every capability-bearing successful HTTP emission is
preceded in the same request trace by the sole share read and sole partial
producer.

**Confinement lemma.** The share is read only as the producer argument; the
successful payload exposes only the partial/proof representation.

**Lifecycle lemma.** Sensitive operator fields are assigned only by the
constructor.  The signed response and coordinator comparison bind the declared
runtime digest.  Lifting that digest equality to byte identity uses the runtime
premise in Section 1.

**Delivery lemma.** Every usable delivery follows threshold reconstruction,
successful commitment verification, and exact named-buyer equality.

Each lemma follows from the statement simulation lemma plus the corresponding
direct structural predicates.  Critical AST hashes are not premises.

## 7. Restricted-source sound simulation theorem

**Theorem.** Let `S` be accepted by the RSP-V6.1 control profile and let
`S_loaded` be byte-identical to `S_cert`.  Under the documented CPython 3.11 and
allowlisted standard-library semantics, for every admitted input `i`,

```text
alpha(Exec_CPython_3_11(S, i)) is a subset of Trace_RSP_V6_1(S, alpha(i)).
```

Consequently every concrete execution satisfies the source-level parts of LC1,
LC3, LC5, and LC7.

**Proof.** Apply the statement simulation lemma to each request callback and
the fixed coordinator/delivery call graph.  The producer, confinement,
lifecycle, and delivery lemmas establish the four obligations on every
projected per-request trace.  R-THREAD preserves them under arbitrary request
interleaving.

## 8. Bounded differential validation

`differential_validate_rsp.py` is a separate executable validation of the rule
semantics, not a proof of the theorem.  It exhaustively generates the bounded
grammar through constructor depth two, compiles every generated program with
CPython 3.11, executes every program under all four valuations of two Boolean
guards, and compares the concrete projection with an independently implemented
RSP evaluator.

The frozen run contains 9,163 legal programs and 36,652 concrete executions.
All traces agree.  Six deliberately wrong rule implementations--both branches,
one loop iteration, skipped exception handler, dropped call body, return
fall-through, and reversed sequence--are each separated by a concrete witness.
An initially generated nested acquisition of the same non-reentrant Lock
blocked concretely; it was correctly removed as outside the accepted grammar
and became an explicit rejection rule in Section 3.

## 9. Evidence hierarchy and nonclaims

The theorem and direct structural predicates carry the source-soundness claim.
The V5-to-V6 delivery repair is evidence that the analysis found a real semantic
mismatch.  The bounded differential run validates the rule implementation.
The CPython bytecode pass is a cross-representation check.  Bandit is retained
only as generic hygiene evidence in the older V6 package.

None of these establishes interpreter, standard-library, operating-system,
native-runtime, hardware, side-channel, dealer-erasure, independent-control,
off-language, or deployment-wide security.
