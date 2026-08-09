# RSP-V6.2 sound-simulation supplement

This artifact strengthens the source-soundness argument for the already frozen
two-host V6 run.  It does not modify the application bytes or wire protocol and
does not require another physical Host 2 execution.

The supplement addresses four distinct questions:

1. `verify_control_profile.py` reparses the exact source bytes inside the V6
   public archive and derives sixteen structural premises.  It checks the
   exception, loop, callback, thread, descriptor, and privileged-site profiles.
   AST digests are identity commitments only.
2. `verify_effect_profile.py` recursively closes the event-relevant call graph
   and classifies every call, assignment, operator invocation, and external
   sink.  R-SILENT is available only to proved event-pure sites; network,
   filesystem, stdout/stderr, logging, environment, IPC, clock, randomness,
   scheduler, thread, and state effects remain explicit.
3. `RSP_V6_2_SOUNDNESS.md` proves a request-indexed CPython-to-RSP simulation
   and its global shuffle-closure form by statement induction.  LC1, LC3, and
   LC7 are request-local; LC5 is a global lifecycle invariant.
4. `differential_validate_rsp.py` exhaustively generates a bounded Python
   grammar, compiles and executes each program with CPython 3.11, and compares
   the projected trace with a separately implemented RSP evaluator.

## Frozen validation result

The bounded grammar contains 9,163 legal programs through constructor depth
two.  Two Boolean guards produce four inputs per program, for 36,652 concrete
CPython executions.  Every projected trace equals the RSP trace.  Six wrong
rule implementations are each rejected by a concrete witness:

- execute both branches;
- force one loop iteration;
- skip an exception handler;
- drop a fixed local-call body;
- let return fall through; and
- reverse sequence order.

The generator initially admitted nested acquisition of the same non-reentrant
`threading.Lock`; concrete execution blocked.  The accepted grammar now rejects
that form explicitly.  This is retained in the proof narrative because it
demonstrates that the concrete semantics, rather than an expected answer, drove
the grammar correction.

## Reproduction

Prerequisites: CPython 3.11 and the sibling
`artifact/paid_threshold_response_two_host_v6` module.

From the repository root:

```text
py -3.11 -B artifact/rsp_soundness_supplement_v2/verify_supplement.py
```

Expected final line:

```text
RSP_SOUNDNESS_SUPPLEMENT=PASS
```

The verifier checks `MANIFEST.sha256`, recomputes the sixteen-condition control
profile and complete effect-site profile from the frozen V6 archive, reruns all
36,652 differential executions, and byte-compares all regenerated JSON objects
with the frozen results.

## Evidence hierarchy

The statement-simulation proof and direct structural predicates carry the
source-soundness claim.  The V5-to-V6 buyer-guard repair is real bug-discovery
evidence.  Differential validation tests the rule semantics, while the existing
CPython bytecode pass is only a cross-representation check.  The older Bandit
record remains generic hygiene evidence and is not a premise of the source
obligations.

The supplement does not prove CPython, the standard library, the operating
system, the native runtime, hardware isolation, secure erasure, independent
economic control, off-language routes, or deployment-wide refinement.
