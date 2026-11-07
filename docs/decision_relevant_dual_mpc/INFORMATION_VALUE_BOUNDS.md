# Decision-relevant upper bounds

## Generic pruning (not novel)

If \(L\le V^\star\) is a verified incumbent lower bound and \(\overline Q(a)\ge Q^\star(a)\) with \(\overline Q(a)\le L\), prune \(a\).

## Ordering (clarified)

A resource relaxation of a clairvoyant continuation is typically **looser**:

\[
Q^\star(a)\le Q_{\mathrm{clairvoyant}}(a)\le \overline Q_{\mathrm{resource}}(a)
\]

when the resource envelope further relaxes the clairvoyant plan family. That is acceptable if the resource bound is much cheaper. The research question is total compute, not tightness alone.

OTUB targets the stronger structural goal

\[
Q^\star(a)\le \overline Q_{\mathrm{OTUB}}(a)\le \overline Q_{\mathrm{DRUB}}(a)
\]

with the second inequality **proved only as a family-restricted empirical/structural goal** (holds on uninformative exploit in the baseline toy because OTUB forbids θ-contingent C while DRUB allows it).

## Bound inventory

| Bound | Status | Scope |
|-------|--------|-------|
| DRUB (clairvoyant OL) | Valid reference UB | Declared plan family |
| REUB_v0 direct-only | **INVALID** | Charging counterexample |
| REUB_v1 charge envelope | Valid family UB | Single-EV `{A,C,S}` |
| OTUB | Valid family UB; `UNSUPPORTED_BOUND` else | Same family; common pattern if ambiguous |
| Zero-VoI certificate | **WITHDRAWN_UNSOUND** | — |

Details: `OBSERVATION_TIMING_THEOREM.md`.

## Incumbent L

Executable Bayes value under nonanticipative continuations only. Never \(\min_\theta\max_\pi R\).
