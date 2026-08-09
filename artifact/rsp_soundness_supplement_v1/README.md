# RSP-V6.1 sound-simulation supplement

This artifact strengthens the source-soundness argument for the already frozen
two-host V6 run.  It does not modify the application bytes or wire protocol and
does not require another physical Host 2 execution.

The supplement addresses three distinct questions:

1. `verify_control_profile.py` reparses the exact source bytes inside the V6
   public archive and derives sixteen structural premises.  It explicitly
   checks exception, loop, context-manager, callback, thread, descriptor,
   decorator, and privileged-site profiles.  AST digests are treated only as
   identity commitments.
2. `RSP_V6_1_SOUNDNESS.md` states the concrete CPython-to-RSP trace simulation
   and proves it by statement induction.  Fixed local calls are structurally
   inlined; no semantic summary is assumed merely because its AST hash matches.
3. `differential_validate_rsp.py` exhaustively generates a bounded Python
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
py -3.11 -B artifact/rsp_soundness_supplement_v1/verify_supplement.py
```

Expected final line:

```text
RSP_SOUNDNESS_SUPPLEMENT=PASS
```

The verifier checks `MANIFEST.sha256`, recomputes the sixteen-condition control
profile from the frozen V6 archive, reruns all 36,652 differential executions,
and byte-compares both regenerated JSON objects with the frozen results.

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
