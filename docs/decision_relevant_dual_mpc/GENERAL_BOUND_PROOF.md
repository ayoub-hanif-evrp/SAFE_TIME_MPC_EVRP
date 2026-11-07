# Generic time–energy–information resource bound

Implementation: `dr_dual/generic/general_bound.py`  
Status API: `VALID_BOUND` | `UNSUPPORTED_BOUND` | `PROVEN_INFEASIBLE` | `UNKNOWN`

## Declared model

Finite road network with named segments; discrete θ support; controller belief; atomic travel/serve/charge/accept; observations only after completed travel; optional depot-return contract.

## Construction

For first travel action \(a\):

\[
\overline Q_{\mathrm{gen}}(a)=\mathbb E_\theta\Big[r_{\mathrm{travel}}(a,\theta)+R_{\mathrm{opt}}(x_a(\theta),S_a(\theta))\Big]
\]

where \(S_a(\theta)\) is the posterior support after \(a\), and \(R_{\mathrm{opt}}\) sums rewards of all pending announced/accepted customers that are **optimistically reachable** from the post-travel node under min segment energies/times over \(S_a(\theta)\), allowing at most one full charge.

If an **accepted** commitment is not optimistically reachable → `PROVEN_INFEASIBLE`.

## Proposition

**Claim.** Under the declared model and finite action class of the generic exact reference, \(Q^\star(a)\le \overline Q_{\mathrm{gen}}(a)\) whenever the bound returns `VALID_BOUND`.

**Proof sketch.**

1. The travel term equals the exact expected first-action reward used by \(Q^\star\).
2. Any feasible causal continuation collects a subset of pending customer rewards (minus nonnegative energy costs). Ignoring future energy costs is optimistic.
3. Counting **every** optimistically reachable pending customer (even if mutually exclusive in a single plan) only increases the envelope, so \(R_{\mathrm{opt}}\ge\) any single feasible continuation’s customer-reward total.
4. Reachability uses min energy/time over the information set and an optional charge — if a true plan reaches a customer under some θ in the set with a common or contingent policy consistent with \(S\), the optimistic graph search also declares reachability.
5. Therefore \(\overline Q_{\mathrm{gen}}(a)\ge Q^\star(a)\).

## What is relaxed

- Future energy costs
- Mutual exclusion among customers (sum vs sequence)
- Exact charge timing beyond one full charge
- Multi-vehicle coupling beyond the acting vehicle’s local envelope

## What is not claimed

- Uniform dominance over clairvoyant DRUB
- A general continuous EVRP theorem
- Computational superiority without the scaling study

## Falsification

Any `VALID_BOUND` value strictly below exact \(Q^\star\) on a tractable instance invalidates certified pruning with this bound.
