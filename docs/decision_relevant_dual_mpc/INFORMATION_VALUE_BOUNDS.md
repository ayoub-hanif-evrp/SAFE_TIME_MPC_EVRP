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

### Zero decision-relevance certificate

If for every \(\theta\), \(V_{\mathrm{OL}}(x_a(\theta),\theta)=V_{\mathrm{robust}}(x_a(\theta),b)\) with belief frozen at the prior, learning cannot improve the continuation family after \(a\). Combined with DRUB \(\le L\), such informative detours are pruned.

### What is / is not claimed

- **Claimed:** soundness under the listed assumptions; empirically valid vs exact \(Q\) on the single-EV network; prunes a zero-VoI informative decoy without losing the optimum.
- **Not claimed:** a fundamentally new relaxation beyond clairvoyant-after-\(\theta\) OL; journal-ready dominance theory; scalability proofs.
