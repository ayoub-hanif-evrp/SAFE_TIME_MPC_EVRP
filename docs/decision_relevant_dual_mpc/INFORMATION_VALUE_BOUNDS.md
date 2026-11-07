# Decision-relevant upper bounds

## Generic pruning (not novel)

If \(L\le V^\star\) is a verified incumbent lower bound and \(\overline Q(a)\ge Q^\star(a)\) with \(\overline Q(a)\le L\), prune \(a\).

## DRUB (clairvoyant / perfect-information reference)

For first travel action \(a\):

\[
\overline Q_{\mathrm{DRUB}}(a)=\mathbb E_{\theta\sim b}\big[r_{\mathrm{travel}}(a,\theta)+V_{\mathrm{OL}}(x_a(\theta),\theta)\big]
\]

with \(V_{\mathrm{OL}}\) the best open-loop continuation in the **same finite plan family** as the exact oracle.

**Soundness (conditional on family):** After informative travel with Dirac posterior, DRUB equals the Bayes continuation; after uninformative travel, θ-contingent OL is optimistic vs nonanticipative common continuation, so DRUB ≥ causal \(Q^\star\).

**Novelty:** none claimed for perfect-information relaxations alone.

## REUB_v0 (direct-only) — INVALID

**Counterexample:** post-corridor SOC cannot reach C directly, but A→S→charge→A→C is feasible within C's window. Direct-only envelope omits C and returns a value **strictly below** true causal \(Q^\star\). See `charging_makes_old_resource_bound_invalid()`.

## REUB_v1 (optimistic charge envelope) — claimed for declared family only

### Declared model

Single EV; customers \(\{A,C\}\); one charger \(S\); continuation family = {stop after A, direct AC, AS+charge+SA+AC}; rewards = customer rewards − energy cost; first action is a D→A corridor.

### Construction

\[
\overline Q_{\mathrm{REUB_v1}}(a)= -c\,e_{\min}(a) + r_A + r_C\cdot\mathbf{1}\{\exists\text{ optimistic direct or charge-then-C path}\}
\]

where \(e_{\min}\) is the minimum corridor energy over θ-support, and reachability uses **minimum** segment energies / optimistic charge time (full charge from post-min-energy SOC).

### Proposition (family-restricted)

**Claim.** For every first corridor \(a\) in the declared model, \(Q^\star(a)\le \overline Q_{\mathrm{REUB_v1}}(a)\).

**Proof sketch.** Any feasible realization under any θ earns at most \(r_A+r_C\) minus nonnegative energy costs. The first-action energy cost is at least \(c\,e_{\min}\). Customer C's reward appears in \(Q^\star\) only if some plan in the family serves C under the (possibly nonanticipative) continuation; if that plan exists for some θ, the optimistic min-energy / min-time relaxation also declares C reachable, so REUB_v1 includes \(r_C\). If no family plan serves C under any θ, neither \(Q^\star\) nor REUB_v1 includes \(r_C\). Hence REUB_v1 dominates every path reward and its belief expectation \(Q^\star\).

**Limits.** Not proved for general multi-customer graphs, partial charge policies outside the family, or multi-EV coupling. Empirically often **looser** than DRUB on the toy (so not yet a strong acceleration device).

### Certification policy

- Do **not** “certify” REUB by comparing to DRUB on every instance.
- Certified pruning may use DRUB, REUB_v1, or `min(DRUB, REUB_v1)` (`bound_mode=combined`) only when the chosen bound’s hypothesis applies.
- Zero-VoI certificate remains **WITHDRAWN_UNSOUND**.

### Incumbent L

L = Bayes value of an **executable** first action under nonanticipative continuations. Never \(\min_\theta\max_\pi R\).
