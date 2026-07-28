# Phase-one claim boundary

This artifact is a controlled RQ2 mechanism instance, not a production
deployment and not a seven-operator decentralization result.

## Certified statement

Let the frozen 4-of-7 committee have bond vector \(P\). Assume that every
usable premature share in the covered mechanism class produces:

1. a public artifact bound to the release job and signed by the bonded
   member's accountability key;
2. a validity attestation signed by the configured evidence verifier;
3. a submission that reaches the chain before the release deadline; and
4. normal chain execution and data availability.

For any successful covered early reconstruction using a distinct-member set
\(S\), \(|S|\geq 4\). Every \(i\in S\) loses its complete bond \(P_i\), so

\[
L(S)=\sum_{i\in S}P_i
\;\geq\;
\sum_{j=1}^{4}P_{(j)}.
\]

With seven uniform 2 ETH bonds, the phase-one lower bound is 8 ETH. The
0.1 ETH caller reward per artifact changes who receives the forfeited amount;
it does not reduce the member's loss.

This statement is invariant to whether the four covered artifacts are
submitted sequentially, in one atomic package, or in repeated packages. The
contract accepts any atomic package size from one through seven, so the claim
does not rely on an externally estimated package-size bound \(b\).

## Deliberately not certified

- Silent raw-share transfers that never create the required signed public
  artifact.
- A malicious or unavailable evidence verifier.
- Censorship that prevents evidence from reaching the chain before release.
- Production bond calibration, real attacker budgets, or market opportunity
  cost.
- Organizational independence, host independence, geographic independence,
  or correlated-failure resistance among the seven test keys.
- Continued committee security after four members are slashed. The
  post-attack current certificate correctly falls to zero and the committee
  must be rotated.

The result is therefore a **positive scoped mechanism certificate**. It
removes the package-bound dependency inside the covered Trace-Then-Slash
mechanism, but it is not yet a production economic certificate.
