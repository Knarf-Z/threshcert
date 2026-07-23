# ThreshCert artifact changelog

## 2026-07-23 eleventh pass: `references.bib` was missing from both trees

While recompiling the paper to verify the tenth pass's Chiado additions
hadn't pushed the body past 15 pages, `bibtex` reported 40 "didn't find a
database entry" warnings. Investigation found `paper/references.bib` --
the actual bibliography source, containing every citation the paper
uses -- did not exist anywhere in either tree (nor in any location on this
machine that could be searched), and had evidently been missing for some
time; MiKTeX's on-the-fly install silently substituted an unrelated file
of the same name from its own package cache, so every prior `pdflatex`
compile this session (including the ninth pass's "confirmed 15 pages by
direct PDF inspection") ran against a broken bibliography without
producing a hard error -- every `\cite` rendered as an unresolved
reference and the printed page count for the body was measured against a
near-empty References section, not a real one. The user supplied the real
`references.bib` content directly. Restored it to both trees (40 entries,
matching every citation key `bibtex` had flagged as missing, zero left
over on either side), reran the full `pdflatex` -> `bibtex` -> `pdflatex`
-> `pdflatex` cycle, and confirmed body length is genuinely **15 pages**
with a properly resolved 40-entry reference list (total document length
rose from 67 to 69 pages once real citations replaced the placeholder
ones, confirming the earlier measurements really had been running against
a broken bibliography). Re-ran the dangling-cross-reference checker (still
0 missing) and cleaned up LaTeX build artifacts in both trees.

**Lesson for future page-count verification passes**: a `bibtex` run that
reports zero "didn't find a database entry" warnings is a precondition for
trusting any page-count measurement from that compile, not an optional
side-check -- silently substituted or missing `.bib` files do not hard-fail
`pdflatex`, so a page count can look plausible while resting on a broken
bibliography.

## 2026-07-23 tenth pass: the rewarded Chiado deployment, actually executed

The eighth pass built `BondedKeyperSlasherRewarded.sol` and its supporting
scripts but left them undeployed for lack of a funded Chiado key. The user
supplied one (funding a freshly generated deployer address from an
existing wallet holding leftover balance from the original pilot), so this
pass actually ran the deployment rather than continuing to describe it as
pending.

- **Real, independently-verifiable transactions on Chiado (chain ID
  10200), not a simulation.** Deployed `BondedKeyperSlasherRewarded` at
  `0x7cDC9C1fC1EC5841908dE73391717Cf3381e583a`, registered the same
  seven-Keyper committee used by the original pilot, froze it (initial
  certificate `8e16` wei), opened a release job for the same validated
  identity and evidence already on record, and submitted member 0's
  already-validated share as evidence -- all 11 transactions `status:
  success`, independently cross-checked against Blockscout
  (`gnosis-chiado.blockscout.com`), not just the local JSON records.
  Certificate dropped from `8e16` to `6e16` wei; the submitting account was
  paid a `1e16`-wei caller reward against a gas cost of only `933176` wei
  (effective gas price `8` wei/gas on Chiado at execution time, three
  orders of magnitude below the `1e10` wei/gas worst case the reward was
  originally sized against) -- net gain to the submitter after its own gas
  cost: `9999999999066824` wei, positive. This is the "genuinely positive,
  reward-covering certificate" the review's P1 item asked for, not merely
  a mechanically-executable one.
- **Caught and fixed a real bug in `submit-evidence-rewarded.ts`'s own
  arithmetic** while building the certificate for this run:
  `netSubmitterGainWei` was computed as `(balanceAfter - balanceBefore) +
  gasCostWei`, which double-corrects for gas and silently reports the full
  reward regardless of gas cost. Fixed to compute directly from the
  contract's immutable `callerRewardWei` minus the recorded gas cost;
  corrected the one already-recorded value this bug had produced
  (`results/slashing-chiado-rewarded.json`) to match, since that file
  was not yet bound into any certificate at the time -- this session
  built its certificate for the first time, so there was no historical
  record to preserve.
- **New parallel certificate script**,
  `deployment/scripts/verify_chiado_certificate_rewarded.py`, mirroring
  `verify_chiado_certificate.py`'s cross-consistency checks against the
  rewarded run's own records and additionally verifying the
  reward-covers-gas-cost claim arithmetically; a new test,
  `test_machine_readable_chiado_certificate_rewarded`, wires it into the
  standard suite. `contracts/BondedKeyperSlasher.sol` and its historical
  certificate remain completely untouched.
- New parallel script `scripts/open-release-rewarded.ts` (not hash-bound,
  but kept parallel to the un-rewarded `open-release.ts` for consistency
  with the rest of this pass's additive naming).
- Regenerated `MANIFEST.sha256` and reran `reproduce_everything.py` in
  both trees; confirmed `PASS` in each.

## 2026-07-23 ninth pass: a real tightness-proof gap, and back to 15 pages

A fifth review of the eighth pass's draft made one substantive
correctness claim and one page-density complaint, both independently
verified before acting on them (per standing instruction to apply
independent judgment to review demands rather than execute them
literally).

- **A genuine tightness-proof gap, confirmed and fixed.** The review
  claimed the tightness directions of `Theorem evidence-optimal-atomic-bypass`
  and `Theorem master-certificate-boundary` cannot literally use the
  "exact-floor profile" `(R-bar, tau-bar)` as a canonical profile, since
  the model defines `tau_i := inf{alpha : R_i <= v_i(alpha)}` with
  `v_i >= 0`, forcing `tau_i = 0` whenever `R_i = 0` -- so a member with
  `R-bar_i = 0 < tau-bar_i` cannot be realized by any actual profile with
  `R_i = R-bar_i` exactly. Verified directly against the paper's own
  model definitions and cross-checked against `Theorem
  information-boundary`'s own (correct) tightness construction and
  `Proposition partial-profile-evidence`'s own proof, which already
  documents this exact degeneracy and uses an epsilon-perturbed profile
  with a limit epsilon-to-0 instead. Both newer theorems' appendix proofs
  had skipped that step and claimed exact attainment directly -- a real
  gap, not a review hallucination. Fixed both tightness proofs with the
  same epsilon-perturbation technique already established and correct
  elsewhere in the paper; softened the two "the exact-floor profile...
  attains X exactly" experimental-verification sentences to correctly
  describe what the numerical state-space check verifies (a discrete
  combinatorial identity, independent of the continuous
  profile-realizability question the proof's epsilon-limit resolves). No
  main-text theorem statement changed -- the certified values were never
  wrong, only the proof technique establishing them.
- **Declined the rest of the same review's demands** on inspection: a
  "Master Certificate Theorem" restructuring of Section 5 (already done
  in the eighth pass, and the review's premise that it didn't exist was
  incorrect), a deployment-requirements table, a quantitative
  baseline-comparison table, and converting more inline definitions to
  display equations on the already-full page 10 (display equations cost
  more vertical space than inline text, directly working against the
  page-budget fix below -- a real tension the review did not
  acknowledge).
- **Main body restored to exactly 15 pages**, verified by direct PDF
  inspection (References now starts on the page immediately after the
  Ethics-considerations paragraph), not by the `\typeout`-based marker
  used in the seventh/eighth passes -- that marker is off by one in
  exactly this kind of boundary case, because TeX's page builder ships
  pages asynchronously, so `\thepage` at a `\typeout` can lag one page
  behind where the immediately preceding text actually lands. Merged
  Ethics Considerations into the Conclusion as a `\paragraph` (removing a
  forced `\section` break) and trimmed Limitations, Discussion,
  Conclusion, Introduction, Contributions, and Related Work prose without
  cutting any theorem, proof, or substantive hedge -- confirmed by
  re-running the dangling-cross-reference checker (0 missing) after every
  edit.
- Regenerated `MANIFEST.sha256` and reran `reproduce_everything.py` in
  both trees; confirmed `PASS` in each.

## 2026-07-23 eighth pass: a master certificate theorem and a positive-enforcement deployment target

A fourth review, on the seventh pass's already-compiled 15-page draft,
argued the atomic-bypass/evidence-optimal machinery still read as an
appended result rather than the paper's actual central theorem, that the
path from a zero certificate to a positive one stayed too abstract, and
that the Chiado pilot's own incentive defect (fee exceeds bond) was never
actually fixed. Addressed in priority order:

- **A genuinely new unifying theorem, not a reframing.** The review
  claimed a combined package-power-and-partial-evidence certificate
  `MABC_{b,M}` already existed in the paper; it did not -- only the
  full-evidence case (`M=U0`) had been proved (sixth/seventh pass). Built
  the general object: `MABC_{b,M}(A0) := min` over packages `Q` of size
  at most `b` of package cost plus the partial-evidence certificate MCR
  restricted to `M \ Q` (removing a bought package's own members from the
  certified set, since a package bypasses activation entirely once
  bought). Proved Theorem master-certificate-boundary
  (`C_{m_bypass(b)}(I_{R,tau,M},A0) = MABC_{b,M}(A0)`) by the same
  composition technique already used for the `M=U0` case, substituting
  Proposition partial-profile-evidence for Theorem information-boundary.
  Every certificate this paper proves -- `0`, `TCR`, `MCR_M`, `ACR`,
  `ABC-bar_b` -- is now a boundary case of this one theorem, not five
  parallel results. New verification script
  `verification_scripts/mixed_evidence_atomic_bypass.py`: 2,900 random
  instances (mixed-tau-vector MCR reduction cross-validated against
  independent brute force, tightness, and soundness at random `(b,M)`
  pairs), 0 discrepancies -- catching and fixing a real bug in the
  script's own first draft (the tightness check compared against a
  ground-truth profile using the wrong floor vector).
- **A concrete positive-certificate target, not just a requirements
  list.** Added Corollary positive-deployment-target: a direct
  instantiation of Proposition public-penalty-input for four bonded
  Keypers each backed by one fixed, funded public enforcement procedure,
  giving an explicit lower bound `>= sum of the four smallest (p*P)`
  rather than only prose about what evidence would help.
- **Declined, on inspection, to add:** a separate "deployment requirements"
  table and a "quantitative baseline" table the review also requested --
  both would mostly reformat content already stated compactly in the
  Discussion and Section 7.2 prose, at real page-budget cost, for limited
  additional information; and a two-axis `(b,M)` overview figure, deferred
  as presentational polish lower priority than the theorem itself. All
  three remain available to add if requested specifically.
- **Addressed the Chiado pilot's actual incentive defect with a new,
  parallel contract, not an in-place patch.** The already-recorded
  `certificates/chiado-execution-certificate.json` binds a SHA-256 hash of
  `deployment/contracts/BondedKeyperSlasher.sol` and
  `deployment/scripts/verify-chiado-live.ts` to a real, already-executed
  Chiado deployment (`deployment/scripts/verify_chiado_certificate.py`'s
  `SOURCE_PATHS`); editing those files in place would silently break that
  historical certificate's binding claim. So `BondedKeyperSlasher.sol`,
  `deploy.ts`, `verify-chiado-live.ts`, and `submit-evidence.ts` are
  untouched, and the reward-split design instead lives in new,
  parallel files: `deployment/contracts/BondedKeyperSlasherRewarded.sol`
  (an immutable `callerRewardWei` split at slash time between the caller
  and the treasury, sized against the worst-case recorded gas cost --
  `108,629` gas @ `10,000,000,007` wei/gas ~= `1.0863e15` wei -- with
  roughly a 9x safety margin; a `registerMember` guard that a bond must
  exceed the reward; `SelfSlashNotAllowed` blocking a slashed member from
  claiming its own reward), `deploy-rewarded.ts`, `submit-evidence-rewarded.ts`,
  and a new `RewardedDeploymentFile` schema type. `src/evidence.ts` gained
  one optional, default-preserving parameter (the EIP-712 domain name) so
  the new contract's differently-named domain verifies correctly; this
  file is not hash-bound and the added parameter does not change behavior
  for any existing caller. New parallel test suite
  `test/BondedKeyperSlasherRewarded.ts` (self-slash rejection,
  bond-must-exceed-reward, reward-split balance assertions) alongside the
  original, untouched `test/BondedKeyperSlasher.ts` -- all 15 tests passing
  locally (`npx hardhat test`) in both trees after `npm install`, and
  `verify_chiado_certificate.py` re-confirmed `PASS` against the untouched
  historical certificate. **Not yet executed on Chiado**: no funded
  Chiado-only private key or RPC access exists anywhere in this repository
  (confirmed by inspection -- only `.env.example` placeholders and the
  well-known public Anvil test key scoped to the disposable local chain),
  so an actual positive on-chain certificate for the rewarded contract
  needs the user to supply one. Separately, splitting the seven-Keyper DKG
  itself across at least three independently managed environments (as
  requested) is not achievable through configuration alone -- the current
  harness is one Docker Compose project on one host with every dependency
  wired via Docker-internal DNS -- and would require provisioning
  genuinely separate hosts/networks and rerunning the DKG end to end, both
  outside what this session can provision on its own.
- Installed MiKTeX (`winget install MiKTeX.MiKTeX`) to compile
  `main_text.tex` directly rather than estimate; confirmed the master
  theorem and corollary push the verified body length from 15 to 16
  pages, and applied the same compaction techniques as the seventh pass
  (collapsing display equations, tightening Discussion/Conclusion/Ethics
  prose) without fully closing the extra page -- flagged honestly rather
  than claimed fixed. Regenerated `MANIFEST.sha256` and reran
  `reproduce_everything.py` in both trees; confirmed no dangling
  `\ref`/`\label` pairs.

## 2026-07-22 seventh pass: closing the evidence-optimal gap and fixing a real proof bug

A third detailed review of the sixth pass's generalization confirmed the
math was sound but found a genuine proof gap, a missing appendix anchor
(a literal broken cross-reference in the compiled PDF), a dozen smaller
prose/notation errors, and -- most importantly -- reiterated that the
atomic-bypass hierarchy was still only an *exact-profile* characterization,
not yet connected back to the paper's central evidence-boundary question.
All were addressed:

- **Fixed a real broken reference.** `main_text.tex` cited
  `Appendix~\ref{app:proof-general-package-family}`, a label that did not
  exist anywhere in `appendix_route_b.tex` -- it would have compiled to a
  literal "Appendix ??" in the PDF. Fixed by giving the general-family
  proof its own proper subsection and label, rather than leaving it folded
  into the atomic-bypass subsection's label as before.
- **Fixed a genuine gap in Lemma package-first-wlog's proof.** The
  previous proof showed the reordered (package-first) schedule has the
  same final exposure as the original and is "successful exactly when the
  original is," but did not account for the mechanism's first-crossing
  semantics: moving the package earlier can make the reordered sequence
  cross the threshold *before* reaching the original's own stopping
  point, and continuing past that point is not a valid schedule.
  Rewrote the proof to explicitly truncate the reordered sequence at its
  own first crossing, arguing the truncation cannot raise cost since
  every resistance value is nonnegative -- exactly the fix the review
  proposed. Strengthened the lemma's own statement to match ("every
  successful schedule using package Q has a package-first successful
  schedule of no greater cost," not just "some optimal schedule is
  package-first"). Added an extended `Gamma-hat_seq` (zero once the
  initial-release set alone already reaches threshold) so the closed-form
  formula is well-defined even when a package alone crosses the
  threshold, which the previous version left implicit.
- **Closed the evidence-optimal gap -- the review's central conceptual
  critique.** The atomic-bypass hierarchy answered "given a known private
  profile, what is the exact cost under `m_bypass(b)`?" but not "what can
  a verifier certify from floors alone?", leaving the new machinery
  disconnected from the paper's actual novelty (the information-boundary
  theorem). Added Theorem evidence-optimal-atomic-bypass: under
  `m_bypass(b)`, public evidence alone certifies exactly `0`, resistance
  floors alone certify exactly `TCR` (regardless of `b`), and
  resistance-plus-activation floors certify exactly a new floors-based
  `ABC-bar_b`. The proof composes the already-proved atomic-bypass and
  information-boundary theorems at a shifted initial-release set
  `A0 union Q` for each candidate package `Q`, so it is short and reuses
  existing machinery rather than needing a new argument from scratch.
  New verification script `evidence_optimal_atomic_bypass.py`: 2,440 total
  random instances (tightness, soundness against perturbed profiles, and
  both degenerate boundary layers), 0 discrepancies.
- **A dozen smaller fixes** raised by the same review, all applied:
  renamed the package variable from `P` to `Q` throughout (it visually
  collided with the private profile `P`, already denoted with a script
  P); redefined `b*` as the size of a *smallest* TCR-optimal cover, not
  just "some" cover; fixed `B_b`'s definition to explicitly exclude the
  empty set, consistent with the general family's own
  `B subset 2^{U0} minus {emptyset}`; corrected "strict at every
  intermediate step" to "strict at both nontrivial steps before reaching
  its plateau" (the curve `10,7,4,4,4,4,4,4` is flat from `b=2` onward);
  fixed the Contributions section's "three contributions" undercounting
  four actual bullets; fixed a remaining "the ordered-witness condition is
  necessary" overclaim in the mechanism-scope paragraph (a duplicate of a
  wording bug fixed elsewhere in an earlier pass, missed here); completed
  the abstract's fallback sentence to state the sound certificate is zero
  when mechanism-robust floors are not certified, not just "threshold
  cover is the safe fallback"; added the same missing "otherwise zero"
  branch to the appendix's verifier-workflow table's ordered-witness and
  timing rows; softened "real atomic bribery contracts are bounded in
  practice" (an unsupported empirical claim) to "this paper does not
  claim the deployed protocol enforces any particular value of `b`";
  consolidated the main text's repeated per-check instance counts (640,
  360, 800, 1,500, 240) down to one number per theorem, with full
  breakdowns moved to this changelog, `EXPERIMENTS.md`, and the
  verification scripts' own docstrings.
- **Trimmed main-text length** toward the venue's page budget: moved the
  cardinality-family-redundancy corollary's full statement and proof out
  of the main text into the appendix (main text now states only the
  hierarchy-defining theorem and the collapse corollary that motivates
  fixing `r=1`); compressed the Application Value section, moving the
  continuation-value-cap derivation's full economic argument into the
  appendix (which previously *claimed* to contain it but did not -- a
  second, independent gap this pass also closed) and leaving only a
  pointer in the main text.
- Regenerated `MANIFEST.sha256` and reran `reproduce_everything.py` in
  both trees; confirmed no dangling `\ref`/`\label` pairs anywhere in
  either LaTeX file via a standalone cross-reference check.
- **Verified the actual page count by compiling, rather than estimating.**
  No LaTeX toolchain existed on this machine; installed MiKTeX (`winget
  install MiKTeX.MiKTeX`) and compiled `main_text.tex` directly --
  `main_text.tex` uses the plain `article` class (10pt, 1in margins, only
  common packages), not a custom LNCS `.cls`, so this required no
  additional template files. The real body-only count (measured by a
  `\typeout{\thepage}` marker placed immediately before the
  `\clearpage`/`\bibliography` call, with `\appendix\input{appendix_route_b}`
  excluded from that measurement) came back at 19 pages initially --
  higher than either this pass's own estimate or the prior simulated
  review's 18-page guess. Iteratively re-measured after each further
  round of cuts (per-page character counts extracted via `pypdf` to
  locate exactly which pages were under-full and pinpoint where
  additional trims would actually move the final page boundary, since
  not every cut propagates all the way to the last page) until the count
  reached exactly 15: additional cuts beyond the ones above included
  collapsing adjacent display equations into single blocks throughout
  (`\quad`-separated single-line statements instead of stacked `\[...\]`
  blocks, which carries real vertical-space cost independent of word
  count -- this alone recovered close to a full page), further
  compressing the Conclusion, Discussion, Related Work, and the Model
  section's exposition, and moving the Higher-Order Defensive
  Interactions section's Corollary and Proposition formal statements
  into the appendix (keeping only the headline Theorem and a one-sentence
  summary in the main text, mirroring the treatment already given to the
  general-package-family section). No font size, margin, or template
  change of any kind. Confirmed via a full two-pass compile (with
  `bibtex` and the appendix `\input`) that the complete 67-page document
  (15-page body, 2 pages of references, ~50-page appendix) still
  compiles with zero LaTeX errors and zero dangling cross-references.

## 2026-07-22 sixth pass: generalizing the atomic-bypass hierarchy to arbitrary package families

Following the fifth pass's naming/code corrections, generalized the
one-shot atomic-bypass mechanism (`m_bypass(b)`, a single size-bounded
package, `r=1`) to an arbitrary certified package family `B` with an
explicit repetition budget `r` -- both to answer "why fix the family to a
size cap, and why fix the repetition to one use?" with a proof rather than
an assertion.

- New: Definition (general bypass mechanism `m_{B,r}`), Theorem (exact
  characterization: `Gamma*_{m_{B,r}} = ABC_{B,r} = min` over the `r`-fold
  disjoint-union closure `B^{+r}` of package cost plus the sequential
  remainder), Corollary (cardinality-family redundancy: for
  `B_b = {P : |P|<=b}`, `B_b^{+r} = B_{min(r*b,|U0|)}` exactly, so
  repeating a size-`b` package cap buys nothing a single bigger package
  doesn't already give -- proved via a direct partition argument, not just
  checked), Corollary (unbounded-repetition collapse: any family
  containing every singleton collapses all the way to TCR once
  `r >= |U0|`) -- added to `main_text.tex`
  (`subsec:general-package-family`) with full proofs in
  `appendix_route_b.tex` (`app:proof-general-package-family`, extending the
  fifth pass's exchange argument from one package to `s<=r`
  pairwise-disjoint packages).
- The second corollary is the actual payoff: it proves, rather than
  asserts, that the fifth pass's `r=1` restriction is exactly the boundary
  at which the hierarchy survives -- any family rich enough to rebuild an
  arbitrary set piece by piece (singletons being the minimal such
  richness) erases the whole hierarchy under unlimited reuse. The first
  corollary shows repetition is genuinely vacuous for the cardinality
  family already in the paper, so `ABC_b`'s existing curve
  (`10,7,4,4,4,4,4,4`) already captures everything reachable by repeating
  same-shape packages -- repetition only matters for families that are
  *not* cardinality-closed (e.g. a fixed menu of specific, non-nested
  multisignature contracts), a case this pass verifies computationally but
  does not further characterize.
- New verification script `verification_scripts/general_package_family_hierarchy.py`:
  cross-validates the general closed form against an independent
  state-space computation on 800 random instances using deliberately
  non-cardinality (exotic) families (0 mismatches); confirms the
  cardinality-redundancy corollary against `atomic_bypass_hierarchy.py`'s
  own closed form on 1,500 instances (0 mismatches); confirms the
  singleton-collapse corollary against an independently computed TCR on
  240 instances (0 mismatches). 2,540 total instances, 0 mismatches, all
  exact (Fraction arithmetic), deterministically seeded via `core.py`'s
  `deterministic_seed`. Drafted and cross-validated in scratch first, at
  smaller scale (880 instances), before being finalized at this scale and
  moved into `verification_scripts/` -- no bugs found in this pass, unlike
  the first `ABC_b` draft.
- Updated `verification_scripts/README.md` (new table row, run command,
  result summary) and `EXPERIMENTS.md` item 29's paragraph in both trees;
  mirrored `main_text.tex` and `appendix_route_b.tex` to the bundle.
- Left deliberately light-touch: the abstract, Contributions, and
  Conclusion are not changed by this pass -- the generalization justifies
  an existing restriction rather than introducing a new headline number,
  so it is presented as a strengthening of Section
  `subsec:atomic-bypass-hierarchy`, not as a new top-level claim.

## 2026-07-22 fifth pass: correcting the atomic-bypass theorem's naming and code

A review of the previous pass's `m_batch(b)`/`BCR_b` result confirmed the
closed-form theorem, its exchange-argument proof, the boundary conditions,
and the four-of-seven curve are all correct under the mechanism as actually
defined -- but found three real issues, all fixed before anything further
was built on top:

- **Naming was misleading.** "`m_batch(b)`" and "batch size `b`" read as an
  ordinary per-transaction cap usable repeatedly. The mechanism actually
  defined and proved permits **at most one** atomic package, of size at
  most `b` in total, **across the entire attack** -- allowing unlimited
  repeated size-`b` packages would collapse every `b>=1` straight to TCR
  and erase the hierarchy. Renamed throughout `main_text.tex` and
  `appendix_route_b.tex`: `m_batch(b)` to `m_bypass(b)`, `BCR_b` to
  `ABC_b` ("atomic-bypass cover"), the section/definition/theorem titles
  from "bounded-package"/"batch" to "atomic-bypass", and strengthened the
  definition and every prose mention (abstract, Contributions, Section
  7.2, Conclusion) to say explicitly "at most one ... across the entire
  attack." `verification_scripts/batch_mechanism_hierarchy.py` renamed to
  `atomic_bypass_hierarchy.py` with matching internal renames.
- **The brute-force "ground truth" was not literally mechanism-faithful.**
  It enumerated every target set and continued checking members past the
  first threshold crossing, relying on non-negative costs and separate
  enumeration of truncated subsets to still reach the correct minimum --
  correct, but the docstring's "directly from the mechanism definition"
  claim was stronger than the implementation. Replaced with
  `abc_state_space`: a memoized recursion over (acquired set,
  package-used-or-not) that returns `0` the instant cumulative weight
  reaches the threshold, so every explored path is by construction a
  literal mechanism schedule, not a truncation-argument-dependent one. Same
  0 mismatches on the same 640+360 instances after the rewrite.
- **Seeding used Python's `hash()` on tuples containing string labels**
  (e.g. `hash((n, trial, seed_base, "bd"))`), which is randomized
  per-process for str/bytes (`PYTHONHASHSEED`) -- "deterministic seeded"
  reproducibility claims were not actually reproducible across machines or
  interpreter invocations, only self-consistent within one run. Added
  `core.py:deterministic_seed()` (SHA-256-based, no process-dependent
  randomization) and switched every affected seed call in
  `atomic_bypass_hierarchy.py`, `information_boundary.py`, and
  `partial_activation_evidence.py` to use it. All three scripts re-run
  clean afterward (different underlying random instances, same 0
  mismatches). **Not yet checked or fixed:** `test_equivalence.py`'s own
  `hash((n, wk, trial))` call has the identical pattern (`wk` is the string
  `"uniform"`/`"random"`) -- this is pre-existing code with its own
  already-cited "725 instances, 0 mismatches" numbers, so it was flagged
  rather than silently modified; a decision on whether to fix it is still
  open.
- Softened the previous pass's PASS-message wording ("the package-first
  WLOG lemma holds on every tested instance") to state plainly that no
  counterexample was found in the tested instances and that the lemma
  itself is established analytically by the exchange argument, not by
  these tests -- matching this project's standing rule against letting a
  finite random check read as a proof.

## 2026-07-22 fourth pass: new theorem answering the package-mechanism gap

- Added a genuinely new theoretical result addressing the reviewers'
  central critique (the strongest theorem, ACR, holds only under the
  sequential mechanism, which the paper's own package counterexample shows
  is not mechanism-robust): a bounded-package mechanism hierarchy `BCR_b`
  interpolating between the sequential mechanism (`b=0`, recovering ACR
  exactly) and the all-or-nothing package (`b=|U0|`, recovering TCR
  exactly), where the adversary may use one atomic, activation-free package
  of at most `b` co-signed members plus ordinary sequential acquisition for
  the rest.
  - New: Definition (bounded-package mechanism), Lemma (the package is WLOG
    triggered first, via an exchange argument), Theorem (exact
    characterization `BCR_b(A0) = min over P, |P|<=b, of sum R_i(P) +
    ACR(A0 union P)`, reusing the existing ACR solver as a subroutine
    rather than a new one), and a Corollary (boundary conditions,
    monotonicity, and a strict separation on the paper's own four-of-seven
    counterfactual: `10,7,4,4,4,4,4,4` for `b=0..7`, already exact at
    `b=2`, not only in the unbounded limit).
  - Explicitly scoped as NOT proven: the evidence-optimal (floors-only)
    extension at fixed `b>0`, and the complexity of `BCR_b` for fixed
    `b>0` (weak NP-hardness is plausible by analogy but not established).
    Stated as open in the paper itself, not silently omitted.
  - Added `verification_scripts/batch_mechanism_hierarchy.py`: cross-checks
    the closed form against a mechanism-definition-faithful brute force
    that does NOT assume the package-first lemma (640 random instances, 0
    mismatches), confirms the boundary/monotonicity claims (360 instances,
    0 mismatches), and reproduces the four-of-seven curve exactly. A real
    implementation bug (an unhandled `w(A0)>=t` edge case violating
    `ac_formula_gamma_star`'s own `w(A0)<t` precondition) was caught by
    this cross-check and fixed before the theorem was written into the
    paper -- the first draft run found 26/135 mismatches; after the fix,
    1,000 instances total, 0 mismatches.
  - Updated the abstract, Contributions (new bullet), Section 7.2's
    counterfactual paragraph (full BCR curve replacing the single
    "10 collapses to 4" sentence), and the Conclusion to reflect this
    result. This was developed as a draft (definitions, theorem
    statement, and verification script written and cross-checked in a
    scratch location) before being written into `main_text.tex` /
    `appendix_route_b.tex`, not derived directly in the paper source.
  - This does not resolve whether the deployed Shutter protocol excludes a
    bounded package of any given size -- that scope argument is still
    owed, and the paper says so.

## 2026-07-22 third paper-review response pass: remaining formal overclaims

- Fixed three remaining formal overclaims flagged by a second simulated
  review pass on the previous update:
  - Contributions: "ordered-witness ... conditions ... pin down exactly
    when the top layer holds" (reads as an iff characterization) replaced
    with "gives a sufficient outcome-level condition under which activation
    cover remains sound ... and an atomic-package construction showing
    activation evidence is not generally mechanism-robust without that
    structure" -- matching what Theorem activation-respecting-soundness and
    Proposition activation-not-mechanism-robust actually establish (a
    sufficient condition plus one counterexample).
  - Table~\ref{tab:certificate-summary}: caption changed from "Largest
    sound certificate by evidence and mechanism scope" to "Exact
    certificate boundaries and generally sound lower bounds by evidence and
    mechanism scope"; added a Status column distinguishing "exact and
    evidence-optimal" rows from "sound lower bound" rows; the
    resistance-plus-activation row's condition text corrected from
    "activation floors, profile-class validity unfalsified only" (implying
    ACR needs only activation floors) to "resistance and activation floors;
    canonical profile class assumed but not certified".
  - Conclusion: "absent an ordered witness or profile-class certification,
    threshold cover is the robust fallback" (wrong on two counts -- losing
    the ordered witness only falls back to threshold cover when
    mechanism-robust resistance floors are separately certified, otherwise
    the sound certificate is zero; and losing profile-class certification
    does not by itself force a fallback to TCR, since the per-member MCR
    route can still apply) replaced with the precise three-way statement.
- Reworded the Ethics Considerations disclosure sentence: "disclosed ...
  with no response by the submission date" read badly given same-day
  timing; replaced with language that does not imply a waiting period that
  did not happen.
- Added a seven-row per-member audit table directly to the Production
  Evidence Audit subsection (Table~\ref{tab:member-audit}: resistance,
  activation, and penalty floor status per committee slot, no full
  addresses), pulled from the real audit data in
  `results/production_member_evidence_audit.csv` -- previously this
  breakdown lived only in the artifact, not the main text.

## 2026-07-22 second paper-review response pass: complete paper received

- Received the complete, substantially revised `main_text.tex` and, for the
  first time, `appendix_route_b.tex` directly from the author. The new
  version adds real new theory beyond what existed in the earlier partial
  copy: a partial-activation-floor-evidence certificate MCR (Proposition
  partial-profile-evidence) that interpolates between TCR and ACR when only
  some members' activation floors are certified, its remediation cost
  analysis (monotonicity, an exact target-reachability characterization,
  and a P=NP-hardness argument for exact zero-cost remediation via a
  Turing reduction to activation cover), a conditional-versus-unconditional
  certificate distinction (`C^cond` vs `C^evid`), an engineering-exposure-
  sufficiency design route (anonymizing release channels), and a timing
  gate for the verifier workflow. Replaced both files in `paper/` with
  this version in both trees.
- Re-applied the same three prose fixes from the previous pass onto this
  new base text (the new version had branched before those fixes and did
  not include them): the abstract rewrite (this time 266 words, also
  crediting the new MCR result in one added clause), the Contributions
  section's opening ("None of the individual mathematical patterns... is
  new by itself" replaced with a direct positive framing that doesn't lead
  with self-deprecation), and the introduction's `$870 million` downgrade.
- Added `verification_scripts/partial_activation_evidence.py`, closing the
  gap the main text's own "Verification" paragraph pointed at ("script in
  the supplementary artifact") and the "Limitations" section had flagged as
  missing. On 200 random instances: MCR at `M=empty`/`full` matches
  TCR/ACR exactly (0 mismatches, cross-checked via `core.py`'s existing
  `ac_formula_gamma_star`); MCR never decreases along a random growing-`M`
  chain (0 monotonicity violations); a further 200 instances confirm the
  proposition's own least-favourable-profile construction attains
  `MCR_M + |S*|*epsilon` exactly (0 tightness mismatches); and 1,000
  perturbed profiles confirm soundness (0 violations). Updated the main
  text's "Clean-room reimplementation" paragraph (now covers this
  proposition) and "Limitations" section (removed the now-stale claim,
  added an honest new one: the remediation Turing-reduction's own
  binary-search procedure is not yet separately re-implemented and
  compared against direct brute-force ACR, only the underlying MCR
  characterization is).
- The previous pass's note that `appendix_route_b.tex` (and Table 1's
  caption/column issues inside it) was inaccessible is now resolved --
  the file is present, and its actual verifier-workflow table
  (`tab:verifier-workflow`) already reflects the conditional/unconditional
  split from this pass's math, so the earlier review's caption critique no
  longer applies to the received version.

## 2026-07-22 paper-review response pass

- Filled in the paper's own `[AUTHOR TODO: state the effective gas price...]`
  placeholder in the Chiado pilot discussion with the recorded transaction's
  actual gas cost versus the bond it forfeited, and added a standalone
  additive script, `deployment/scripts/report_slashing_fee_ratio.py`, that
  recomputes the same ratio from the already-recorded
  `results/slashing-chiado.json` without modifying the Chiado execution
  certificate (whose hash is cited by exact value elsewhere): `108,629` gas
  at `10,000,000,007` wei/gas is `1,086,290,000,760,403` wei against a
  `1e12`-wei forfeited bond, i.e. the attestation cost about `1,086x` the
  bond it recovered.
- Updated the generalized committee-shape sweep's two paper paragraphs
  (Section 7's table row and its "Generalization across committee shapes"
  subsubsection) to reflect the six-shape, 600-trial sweep added in the
  2026-07-21 pass (previously only the original four shapes were described
  in the paper text itself, even though the code/CHANGELOG already had six).
- Added one sentence to Section 7's "Independent reimplementation"
  subsubsection describing the new `information_boundary.py` check (added
  2026-07-21) -- previously absent from the paper text entirely.
- In response to a simulated-review pass, rewrote the abstract (324 to 254
  words; dropped the defense-interaction/replacement-hull sentence, kept in
  the introduction and contributions instead) and fixed an overclaim: "activation
  cover remains sound only with an ordered first-crossing witness" (reads as
  a necessity claim) became "we give a sufficient condition under which
  activation cover remains sound... and show by an atomic-package
  counterexample that it is not generally mechanism-robust without it" --
  matching what Theorem~(activation-respecting-soundness) and
  Proposition~(activation-not-mechanism-robust) actually establish (a
  sufficient condition plus one counterexample, not a necessary-and-sufficient
  characterization).
- Added a lead sentence to the Contributions subsection stating the
  contribution directly (exact identification of the evidence-induced robust
  value, applied to a live committee) instead of only listing consequences,
  repositioning the paper's framing toward a verifier-facing audit
  methodology rather than a general economic-security claim.
- Downgraded the introduction's specific "\$870 million" DEX-volume figure to
  a qualitative "substantial production order flow" statement, pointing to
  the appendix calibration section for the actual number -- avoids reading
  as impact inflation on the first page for a figure the paper itself says
  is a scale proxy, not an attack-value bound.
- Table 1 (`tab:verifier-workflow`, in `appendix_route_b.tex`) has separately
  flagged caption/column issues from the same review pass that could not be
  addressed -- that file is not present on this machine.

## 2026-07-21 second upgrade pass

- Extended the generalized committee-shape sweep
  (`scripts/run_generalized_committee_sweep.py`) with two more shapes,
  8-of-15 and 9-of-17 (100 trials each), continuing the existing
  `(5,3),(9,5),(11,6),(13,7)` progression. Purely additive: each shape's
  random draws are independently seeded by `(n, q)`, so the four
  previously-recorded shapes and the original n=7 experiment are unchanged;
  confirmed by rerunning and diffing the four original shapes' printed
  values. Both new shapes were monotone across all 100 trials and greedy
  was exact at budget one and two, degrading at budget three -- the same
  qualitative pattern as the existing four shapes.
- Added a new parallel scaling point, `n=20`, to the machine-specific exact-
  solver benchmark (`scripts/run_scaling_benchmark_extended.py` +
  `scripts/summarize_scaling_repeats_extended.py`), with its own ten-repeat
  raw files and median/IQR summary
  (`results/solver_scaling_repeats_extended*`). Kept separate from
  `scripts/run_scaling_benchmark.py`'s existing n=8..18 table because that
  table's file/row counts are hard-asserted and its summary is consumed
  (byte-compared) by `extended_experiments/`. Median wall time `32.244088` s,
  consistent with the existing growth trend.
- Actually ran and recorded (rather than just documenting as possible) the
  independent-implementation scaling check
  (`verification_scripts/scaling_fast.py`) through n=24, saving the full
  n=8..24 table to the new `verification_scripts/results/scaling_fast_extended.txt`
  (n=24: 16,777,216 states, median 55.99 s).
- Neither new scaling script joins the automatic `reproduce_everything.py`
  chain, consistent with the existing exclusion of machine-specific timing
  benchmarks from that chain.
- Received the paper's full `main_text.tex` directly from the author and
  saved it to `paper/main_text.tex`, closing the "paper source not on this
  machine" gap noted for every theorem except the replacement-hull one
  (confirmed the previously pasted replacement-hull theorem statement
  matches `main_text.tex` exactly; `appendix_route_b.tex`, containing the
  proofs, is still not present).
- Added `verification_scripts/information_boundary.py`, independently
  stress-testing the paper's central theorem (evidence-optimal certificates
  under activation scope). Unlike `test_equivalence.py` (which checks the
  (AC) reduction for one fixed profile), this tests the theorem's actual
  claim about an evidence ledger: on 300 random small instances (n=3..7),
  the exact-floor profile attains TCR/ACR exactly (tightness), and 1,500
  further profiles built strictly above the same floors -- resistance and
  activation independently perturbed upward, including the
  most-permissive all-zero-tau case for the mechanism-robust TCR claim --
  never certified a smaller attack cost (soundness); a separate 60-instance
  check confirms the public-only layer collapses to exactly zero. Not part
  of the routine reproduction chain (same tier as `replacement_hull.py` and
  `scaling_fast.py`).

## 2026-07-20 pre-submission hardening pass

- Merged this working tree with the parallel `FC_complete_experiment_bundle`
  distribution, which had independently gained an independent from-scratch
  reimplementation (`verification_scripts/`) that cross-checks the paper's
  own numbers; that suite was ported in, and this tree's production evidence
  audit, Gnosis counterfactual, and Chiado execution certificate were ported
  the other way so both stay at feature parity.
- Added a generalized committee-shape sweep
  (`scripts/run_generalized_committee_sweep.py`) that repeats the seeded
  random monotonicity, Möbius truncation-error, and exact-vs-greedy
  allocation checks at four additional committee shapes (3-of-5, 5-of-9,
  6-of-11, 7-of-13, 100 trials each), so the n=7 findings are not read as an
  artifact of the one committee size the paper headlines. Truncation error is
  computed via a per-order zeta-transform accumulation rather than the
  original `O(3^n)` per-mask routine, keeping the check cheap up to n=13; the
  faster routine was cross-checked exactly against the original for `0`
  mismatches on a held-out instance.
- Added a boundary and larger-committee sensitivity sweep to
  `extended_experiments/` (`parameter_sensitivity_boundary.csv`, 64 rows):
  degenerate threshold margins (`q=1`, `q=7`), an all-zero and a
  single-dominant-member resistance profile, and committee sizes 14 and 28
  built by tiling the original profile shapes. Kept separate from the
  existing 48-row table so its row count and recorded numbers are unchanged.
- Added `reproduce_everything.py` at the artifact root, chaining the four
  previously separate reproduction entry points
  (`scripts/reproduce_all.py`, the new generalized sweep,
  `extended_experiments/reproduce_extended.py`, and the
  `verification_scripts/` suite) plus the offline Chiado certificate check
  into one `everything=PASS` command.
- Re-ran the live production-snapshot recheck and the live Chiado recheck;
  both still returned `PASS` against current chain state as of this pass.
- Added `verification_scripts/replacement_hull.py`, closing the one
  previously-unexercised item in that suite's own limitations list: the
  replacement-hull attribution theorem (public-attribution-formal-bounds),
  from the theorem statement supplied directly by the paper's author since
  `main_text.tex` is not on this machine. Checks the primal (lambda) formula
  against the equivalent (s, Q in conv(R)) formula for `A_i^eps(C,x)` on 200
  random instances via an exact Fraction-equality check (not tolerance-based:
  extracts `s*` from the primal LP's own optimal solution and independently
  re-solves the other formula's inner problem at that exact value), plus the
  separation corollary on three hand-picked constructive instances. Not part
  of the routine reproduction chain (takes ~45 seconds; run separately, like
  `scaling_fast.py`).
- Regenerated `MANIFEST.sha256` after the merge and additions; every
  reproduction layer, including the seven-test deployment suite, passes.

## 2026-07-19 pinned-geometry counterfactual branch check

- Added a deterministic seven-member, four-of-seven counterfactual fixture
  bound to the pinned Gnosis committee geometry, with explicitly hypothetical
  resistance and activation floors in normalized cost units and a separate
  counterfactual ledger.
- Added strictly conditional paper language for the `0 -> 4 -> 10` evidence
  layers, plus synchronized limitations and conclusion language; the actual
  production ledger remains zero.
- Ran the existing exact subset-state solver through the public, TC, AC, and
  robust-fallback branches, recording `0 -> 4 -> 10 -> 4`, TC cover
  `{2,3,4,5}`, and AC witness `(0,1,2,3)`.
- Checked all 21 seed-member placements and verified that disabling either the
  ordered-witness or exposure-sufficiency gate suppresses the AC value and
  returns the separable-payment TC fallback of `4`.
- Added a portable result JSON, exact expected stdout, five regression tests,
  and root-reproduction integration. No Chiado or production-chain experiment
  was rerun.
- Fixed the retained production-audit JSON writer to emit UTF-8/LF bytes on
  every operating system, preventing Windows/Linux manifest drift.

## 2026-07-19 production deployment evidence audit

- Replaced the date-only production snapshot with an archival anchor at Gnosis
  block `46,666,718` and recorded its hash, manager, active set, activation
  block, creation and registration transactions, threshold, and seven real
  member addresses.
- Added a seven-row evidence ledger covering direct resistance, activation,
  attribution, forfeiture, joint execution probability, and insurance or
  compensation for every production Keyper.
- Added deterministic evidence gates and per-member result files. The audit
  distinguishes unknown actual resistance from a zero certified floor and
  reports that four additional positive member floors are needed for any
  positive four-of-seven certificate.
- Added a standard-library archival-RPC verifier for the fixed block, set
  state, creation receipt, and `KeyperSetAdded` event.
- Integrated the production audit into the root reproduction command and added
  tests showing that unsupported numerical claims and nominal penalties cannot
  enter the certificate.

## 2026-07-19 machine-readable Chiado execution certificate

- Added a deterministic certificate that binds the recorded 4-of-7 Rolling
  Shutter evidence, Chiado transaction trail, contract, exporter, Keyper set,
  and live verifier by SHA-256.
- Added an offline verifier that recomputes the exact four-smallest-bonds value
  before and after slashing and rejects stale or cross-inconsistent records.
- Integrated certificate verification into the root reproduction command,
  bundle-integrity tests, and deployment acceptance command.
- Encoded the claim boundary inside the certificate: the `3e12`-wei value is
  positive within the controlled public-testnet mechanism, while production
  Shutter resistance, activation, and enforcement probability remain
  `NOT_CERTIFIED`.

## 2026-07-17 complete hardened bundle

- Fixed cross-version byte reproducibility for the four seeded random-lattice
  CSV files by making floating-point accumulation order explicit. The outputs
  now match the recorded Python 3.11 baseline when reproduced on Python 3.11
  or 3.12.
- Preserved the complete original experiment code and recorded results.
- Kept scalability, parameter sensitivity, and baseline comparison isolated in
  `extended_experiments/`.
- Added read-only Chiado verification of 11 transaction receipts, exact
  creation bytecode and constructor arguments, live committee state, slashing
  calldata, and the emitted event.
- Expanded Solidity tests to cover nonuniform bonds and binding of every
  verifier-signed evidence field.
- Expanded the Go evidence exporter checks for duplicate and out-of-range
  Keyper indices and stronger instance/eon/identity binding.
- Added public Dune query links while retaining the explicit limitation that
  the archived raw SQL was not included.
- Added citation metadata for Jiaqi Zhang and Honghao Fu.

## Earlier artifact update: defense lattice and Möbius experiments

## Added

- Exact Boolean-lattice Möbius and inverse transforms.
- Exact sequential solver for the coordinated-defense construction.
- Pure high-order interaction and low-order truncation experiments.
- One hundred seeded random uniform four-of-seven certificate instances.
- Exact versus singleton-marginal greedy allocation checks.
- A fixed-family decoy construction exposing arbitrarily poor greedy gain.
- Minimal target-achieving remediation-plan enumeration.
- Unit tests and a single deterministic reproduction entry point.
- Controlled penalty-evidence gate checks.
- Supplied Dune/GPv2 exports, provenance limitations, validation, and a
  calibration-only summary.
- A complete experiment inventory and explicit list of missing deployment
  artifacts.
- Ten retained exact-solver scaling repeats, hardware metadata, and a
  deterministic median/IQR summary.
- A seven-process 4-of-7 Rolling Shutter v1.4.4 deployment overlay with fresh
  runtime keys and DKG readiness checks.
- A Go evidence exporter that validates Shutter BLS shares, native Keyper
  signatures, aggregate-key validity, and four-share reconstruction.
- A verifier-gated bonded-Keyper Solidity contract, six Hardhat tests, and
  Chiado scripts that record the complete public transaction trail.

## Corrected

- Defensive-allocation values are now computed rather than copied from a
  documented table. The detailed output records every member increment and all
  four minimal-cover costs.
- Machine-specific scaling output is excluded from the immutable hash manifest.
- The activation-ladder exposure column no longer emits a binary floating-point
  representation such as `0.30000000000000004`.

## Completed public pilot

- Added the returned Chiado deployment, release-job, validated seven-share
  evidence, and slashing records from the completed user-run experiment.
- Recorded public contract
  `0x3C16dd5689D67d51c076fe80CB7189041c107721` and successful slashing
  transaction
  `0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd`.
- Added cross-record integrity tests and portable artifact references.

The production evidence audit supports a zero certified lower bound while
leaving actual resistance unknown. The completed single-host controlled pilot
is a separate implementation experiment and does not establish production
resistance values or independent operator governance.
