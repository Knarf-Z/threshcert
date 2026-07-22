# Independent verification scripts

From-scratch reimplementation of the paper's core algorithms, built only
from the formulas in `main_text.tex` / `appendix_route_b.tex` -- **not**
from the authors' own (unseen) code. Used to independently cross-check
every named number in Section 7 and to random/exhaustively stress-test the
central theorems beyond the paper's own hand-picked examples.

No third-party packages are used -- only the Python standard library
(`fractions`, `itertools`, `random`, `time`, `statistics`, `math`). Any
Python 3.8+ works.

## Running on Windows PowerShell

Open PowerShell, `cd` into this folder, then run each script with
`python` (or `py`, depending on your install):

```powershell
cd path\to\verify
python .\test_equivalence.py
python .\reproduce_paper_numbers.py
python .\hardening_and_greedy.py
python .\instability.py
python .\scaling_fast.py --ns 8 10 12 14 16 18
python .\replacement_hull.py
python .\information_boundary.py
python .\partial_activation_evidence.py
```

If `python` is not recognized, try `py` instead (`py .\test_equivalence.py`).
Check your install with `python --version` (needs 3.8+).

`core.py` is a shared module (no output by itself) imported by the other
scripts -- keep it in the same folder.

## What each script does

| Script | What it checks | Expected output |
|---|---|---|
| `core.py` | Shared module: brute-force sequential-search `Gamma*`, the independent subset/canonical-order (AC) formula solver, the uniform lower-tail closed form, and a random-instance generator. Not run directly. | (none, imported by others) |
| `test_equivalence.py` | Random cross-validation of the central theorem (`Gamma* == min over T+(A0) of resistance sum`) on 720 random small instances (n=3..8, uniform and non-uniform weights, 60 trials each) plus 5 hand-picked edge cases (all-zero tau, tied tau, zero-resistance members, near-threshold `A0`, an infeasible instance). | `Total instances tested: 725`, `Mismatches: 0` |
| `reproduce_paper_numbers.py` | Reproduces all 36 specific numbers claimed in Section 7 (activation ladder 5/14/23/32/41, mechanism-stress k+4 vs 4, the exact published defensive-allocation instance and its three-rule table, the baseline-comparison numbers 0/4/18/40). | `TOTAL CHECKS: 36   MATCH: 36   MISMATCH: 0` |
| `hardening_and_greedy.py` | Reconstructs the exact appendix instances for the coordinated-hardening / pure-Möbius-interaction theorem and the singleton-greedy-no-guarantee proposition, and checks them **exhaustively** (every subset, not a sample) for several k and M / rho values. | Two `PASS` lines |
| `instability.py` | Reconstructs the exact appendix instance for the activation-boundary-instability theorem; brute-force-checks it for small K and arithmetic-checks the same construction for large K (K up to 1,000,000). | `PASS: True` |
| `scaling_fast.py` | Independent timing benchmark of the exact subset-state solver on random instances, mirroring (not matching wall-clock time with -- different machine/implementation) the paper's own n=8..18 scaling table. Extend with `--ns 20 22` etc.; runtime grows fast (n=22 took ~15s on the machine this was built on), so raise `--ns` gradually. A later pass actually ran and recorded `--ns 8 10 12 14 16 18 20 22 24` (n=24 median 55.99s); see `results/scaling_fast_extended.txt`. | A timing table; states should quadruple and runtime roughly track it for every +2 in n |
| `replacement_hull.py` | Independent verification of the replacement-hull characterization theorem (public-attribution-formal-bounds), originally written from the theorem statement pasted directly by the paper's author, before `main_text.tex` was available on this machine (see limitations below; `main_text.tex` arrived in a later pass and confirms the theorem was transcribed correctly). Checks the primal (lambda) formula against the equivalent (s, Q in conv(R)) formula for `A_i^eps(C,x)` on 200 random small instances (two committee/outcome shapes, five `eps` values) by extracting `s* = sum(lambda*)` from the primal LP's own optimal solution and re-solving the (s, Q)-formula's inner problem independently at that exact `s*` -- an exact Fraction-equality check, not a tolerance-based one. Separately checks the separation corollary (`Q_Cx` outside `conv(R)` iff a separating functional exists) on three hand-picked constructive instances where the functional is exhibited directly. Takes about 45 seconds -- not part of the other scripts' quick run. | `replacement_hull_theorem=PASS`, `formula_equivalence_mismatches=0` |
| `information_boundary.py` | Independent stress-test of the central theorem (information-boundary / evidence-optimal certificates), added once `main_text.tex` became available. `test_equivalence.py` only checks the (AC) reduction for one fixed profile; this script tests the theorem's actual claim about an evidence LEDGER of certified floors: on 300 random small instances (n=3..7), the exact-floor profile attains TCR/ACR exactly (tightness), and 1,500 further profiles built strictly above the same floors -- resistance and activation independently perturbed upward, including the most-permissive all-zero-tau case for the mechanism-robust TCR claim -- never produced a smaller brute-force attack cost (soundness). A separate 60-instance check confirms the public-only layer (zero resistance floor) collapses to exactly zero. | `soundness_violations=0`, `tightness_mismatches=0`, `public_only_mismatches=0` |
| `partial_activation_evidence.py` | Independent stress-test of the newer partial-activation-floor-evidence proposition (the MCR certificate interpolating between TCR and ACR as the ledger certifies activation floors for only some members M), added once the appendix arrived with its proof. On 200 random instances: MCR at M=empty/full matches TCR/ACR exactly (computed via `core.py`'s own `ac_formula_gamma_star`); MCR never decreases along a random chain of growing M (remediation monotonicity); the proposition's own least-favourable profile attains `MCR_M + |S*|*epsilon` exactly via brute-force sequential search (tightness); and 1,000 further profiles built strictly consistent with the same partial evidence -- M-members perturbed upward, non-M members given an unconstrained random activation floor -- never certified a smaller attack cost (soundness). | `boundary_mismatches=0`, `monotonicity_violations=0`, `tightness_mismatches=0`, `soundness_violations=0` |

## Honest limitations

- This reimplementation was built by the same process that edited the
  paper, not by an independent third party -- it can catch implementation
  bugs and transcription errors, but not a shared conceptual mistake that
  both passes would make the same way.
- The replacement-hull attribution theorem (`replacement_hull.py`) was added
  from the theorem statement pasted directly by the paper's author, at a
  time when neither `main_text.tex` nor `appendix_route_b.tex` was present
  on this machine -- this script was not independently derived from the
  paper text the way the others were. Both files have since arrived and
  confirm the pasted statement, and its proof, match
  Theorem~(replacement-hull) exactly. Its separation-corollary check still
  only covers three hand-picked constructive instances (where a separating
  functional is exhibited directly), not a general separating-hyperplane
  solver over random instances the way the formula-equivalence check does --
  writing one from scratch (matching this module's no-third-party-package
  rule) was out of scope for this pass.
- `information_boundary.py` tests only the sequential-offer mechanism's
  three-layer certificate (Theorem information-boundary), not the broader
  mechanism-robust or activation-respecting extensions
  (Theorems activation-respecting-soundness / mechanism-robust-threshold-cover)
  that let the ACR/TCR bounds survive beyond that one mechanism -- those are
  not yet covered by an independent script.
- `partial_activation_evidence.py` checks the MCR characterization and its
  remediation monotonicity, but not the specific zero-cost-remediation
  binary-search reduction used to recover ACR
  (Appendix `app:proof-remediation-monotone`'s "Turing reduction" argument)
  -- that reduction is not yet independently re-implemented and compared
  against direct brute-force ACR computation the way the appendix's own
  text describes checking it.
- The Gnosis production audit and the Chiado testnet pilot
  are on-chain facts, not algorithms -- nothing here re-audits them.
- The mechanism-stress-test instance in `reproduce_paper_numbers.py` is
  this author's own construction satisfying the paper's stated properties
  (k+4 sequential vs 4 package cost) -- the paper's own appendix does not
  pin a single specific set of weights for that example, unlike the
  defensive-allocation instance, which is reproduced exactly.

## Result summary (as last run)

- `test_equivalence.py`: 720 random instances (n=3..8) + 5 edge cases, 725 total, 0 mismatches.
- `reproduce_paper_numbers.py`: 36/36 matched.
- `hardening_and_greedy.py`: coordinated-hardening theorem verified
  exhaustively (all 2^k-1 proper subsets, not sampled) for k up to 9 and
  several M; singleton-greedy proposition verified for k up to 20 and
  several rho, cross-checked against the general solver (0 mismatches).
- `instability.py`: verified for small K by brute force, and by direct
  arithmetic for K up to 1,000,000.
- `scaling_fast.py`: reproduced the paper's O(2^n) growth pattern and
  extended it to n=22 (4,194,304 states, ~15s on the machine this was
  built on), beyond the paper's own n=18 ceiling. A later additive pass
  actually ran and recorded one point further, n=24 (16,777,216 states,
  median 55.99s on the machine this pass was run on -- see
  `results/scaling_fast_extended.txt` for the full n=8..24 table from that
  run, including its own re-measurement of n=8..22).
- `replacement_hull.py`: 200 random instances (two committee/outcome shapes,
  five `eps` values each), 0 formula-equivalence mismatches, all exact
  (Fraction equality, not tolerance-based); all 3 hand-picked separation-
  corollary cases passed.
- `information_boundary.py`: 300 random evidence ledgers (n=3..7, uniform and
  non-uniform weights, 60 per n), 0 tightness mismatches; 1,500 further
  profiles built strictly above those same floors, 0 soundness violations; a
  separate 60-instance public-only check, 0 mismatches (all-zero resistance
  floor collapses to exactly zero certificate in every case). All exact
  (Fraction arithmetic).
- `partial_activation_evidence.py`: 200 random instances (n=3..7), 0
  boundary mismatches (MCR at M=empty/full vs TCR/ACR) and 0 monotonicity
  violations across a random growing-M chain per instance; a further 200
  instances for tightness (0 mismatches against the proposition's own
  least-favourable-profile construction) plus 1,000 perturbed profiles for
  soundness (0 violations). All exact (Fraction arithmetic).
