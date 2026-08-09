# RSP-V6.2 concrete-to-trace soundness supplement

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

A concrete state belongs to one global CPython execution `E`.  It includes the
current source statement, local and object stores, exception or return
continuations, lock state, the finite request/response environment, and a
request identifier on every request-originated step.  We use the documented
Python 3.11 semantics for expression evaluation, calls, `if`, `for`, `return`,
`try`, and `with`, together with the documented `BaseHTTPRequestHandler`,
`ThreadingHTTPServer`, and `threading.Lock` contracts.

The projection `alpha(E)` retains the event-relevant effects and their request
identifiers.  Its request projection `alpha_r(E)` filters those events to
request `r` while preserving concrete order.  The event alphabet contains:

```text
request-entry
share-read
partial-create
http-emit
threshold-combine
commitment-verify
buyer-guard
usable-deliver
network/filesystem/stdout/stderr/logging/environment/IPC effects
clock/random/scheduler/thread/state effects
```

`Trace_RSP_V6_2^r(S, alpha(i_r))` is the prefix-closed set of local traces
derived for request `r`.  `Shuffle_RSP_V6_2(S, alpha(I))` is the closure under
all interleavings that preserve every request-local order and the order of
global lifecycle events.  The request-indexed and equivalent global targets
are:

```text
for every r, alpha_r(E) is in Trace_RSP_V6_2^r(S, alpha(i_r))
alpha(E) is in Shuffle_RSP_V6_2(S, alpha(I))
```

This is a safety simulation.  It does not assert termination.  A concrete
request that blocks or raises before a successful response contributes only
its projected prefix.

## 3. Accepted control profile

RSP-V6.2 accepts the following forms in the event-relevant slice:

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

RSP-V6.2 rejects, in the event-relevant slice:

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

Every call, assignment, operator invocation, and external sink in the
event-relevant call closure is classified by a structural RSP rule or proved
event-pure.  The external-sink alphabet explicitly includes network,
filesystem writes, stdout/stderr, logging, environment mutation, and IPC; it
also retains clock, randomness, scheduler, thread, and state effects.  Calls to
fixed local bodies are expanded recursively.  Operator sites require exact
built-in or allowlisted standard-library operand types, while user dispatch
hooks such as overloaded operators, `__getattribute__`, `__setattr__`, and
descriptors are rejected.

Generators, lambdas, and loops may occur in event-pure support functions only
when the same closure analysis classifies every effect site in their bodies.
This is an explicit effect-closure rule, not an assumption that Python lacks
hidden effects.

## 4. Simulation rules

### R-SILENT, R-EFFECT, and R-OP

R-SILENT applies only after the effect-profile verifier has classified every
call, assignment, and operator reachable from an event-relevant root and has
proved that the current site is event-pure.  “No projected site” is not itself
a premise.

R-EFFECT retains every classified external or state effect in the abstract
trace, including network, filesystem, stdout/stderr, logging, environment,
IPC, clock, randomness, scheduler, thread, and mutable-state effects.  A site
outside this alphabet or without a rule causes rejection.

R-OP applies only where the verifier establishes the exact built-in or
allowlisted standard-library operand type.  Source-defined operator,
attribute, assignment, property, descriptor, or metaclass dispatch hooks cause
rejection rather than silent projection.

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
dynamic import, reflection, and user-defined descriptor hooks.  No arbitrary reviewed summary is substituted.

### R-CALLBACK and R-THREAD

The documented HTTP dispatcher selects the declared `do_METHOD` handler.  The
certified handler class has no custom initializer and exactly the four reviewed
methods.  Each callback receives a request identifier.  R-THREAD admits exactly
the shuffle closure that preserves every `alpha_r(E)` order and the global
lifecycle order.  LC1, LC3, and LC7 are request-local prefix-closed safety
properties.  LC5 is instead a global lifecycle invariant and is checked on the
whole shuffle, with nonce check/update linearized by the allowlisted lock.  No
deterministic thread schedule is assumed.

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
is a prefix of a request trace derived for `s` by RSP-V6.2.

**Proof.** By structural induction on `s`.

- Event-pure calls, assignments, and operators use R-SILENT; every classified
  external or state effect uses R-EFFECT, and typed operators use R-OP.
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

**Theorem.** Let `S` be accepted by the RSP-V6.2 control and effect profiles and
let `S_loaded` be byte-identical to `S_cert`.  Under the documented CPython 3.11
and allowlisted standard-library semantics, for every global execution `E`
over admitted request family `I`,

```text
for every r, alpha_r(E) is in Trace_RSP_V6_2^r(S, alpha(i_r))
alpha(E) is in Shuffle_RSP_V6_2(S, alpha(I))
```

Consequently every concrete execution satisfies the source-level parts of LC1,
LC3, LC5, and LC7.

**Proof.** Apply the statement simulation lemma to each request callback and
the fixed coordinator/delivery call graph.  Effect-site exhaustiveness supplies
a case for every call, assignment, operator, and external sink.  The producer,
confinement, and delivery lemmas establish request-local LC1, LC3, and LC7.
The lifecycle lemma and lock linearization establish global LC5 over the
shuffle closure.  R-THREAD preserves request-local order and global lifecycle
order under every admitted interleaving.

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

The theorem, effect-site closure, and direct structural predicates carry the source-soundness claim.
The V5-to-V6 delivery repair is evidence that the analysis found a real semantic
mismatch.  The bounded differential run validates the rule implementation.
The CPython bytecode pass is a cross-representation check.  Bandit is retained
only as generic hygiene evidence in the older V6 package.

None of these establishes interpreter, standard-library, operating-system,
native-runtime, hardware, side-channel, dealer-erasure, independent-control,
off-language, or deployment-wide security.
