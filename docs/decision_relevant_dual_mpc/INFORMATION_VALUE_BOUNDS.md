# Decision-relevant upper bounds (DRUB)

## Generic pruning (not novel)

If \(L\le V^\star\) is a verified incumbent lower bound and \(\overline Q(a)\ge Q^\star(a)\) with \(\overline Q(a)\le L\), prune \(a\).

## DRUB construction (research object)

For first travel action \(a\):

\[
\overline Q(a)=\mathbb E_{\theta\sim b}\big[r_{\mathrm{travel}}(a,\theta)+V_{\mathrm{OL}}(x_a(\theta),\theta)\big]
\]

with \(V_{\mathrm{OL}}\) the best open-loop continuation in the **same finite plan family** as the exact oracle.

### Soundness (conditional)

Within that family, under deterministic latent regimes and the stated observation model:
- After an informative segment with zero noise, the posterior is Dirac and DRUB equals the exact Bayes continuation value.
- After an uninformative segment, DRUB is optimistic relative to robust causal continuation (θ-contingent OL without further observations), hence still an upper bound on causal \(Q^\star\).

### Zero decision-relevance certificate — WITHDRAWN

Equality of known-\(\theta\) optimal values does **not** imply a common nonanticipative policy (P1/P2 counterexample). Do not prune on that test.

### Incumbent lower bound L

L must be the Bayes value of an **executable** first action under nonanticipative common continuations. Never initialize L from \(\min_\theta\max_\pi R\).

### What is / is not claimed

- **Claimed (conditional):** clairvoyant DRUB ≥ true causal Q in the declared family; pruning with verified executable L retains the exact first action on the single-EV toy; P1/P2 regression.
- **Not claimed:** novel information-relaxation theory; resource envelope as a certified general UB; scalable runtime gains; cross-vehicle VoI.
