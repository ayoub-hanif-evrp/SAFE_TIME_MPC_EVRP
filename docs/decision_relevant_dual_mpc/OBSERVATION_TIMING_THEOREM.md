# Observation-timing upper bound (OTUB)

## Declared model

Single EV; customers \(\{A,C\}\); charger \(S\); first action \(a\) = travel on a named D→A corridor.
Observation time \(\tau_{\mathrm{obs}}(a)=\) corridor travel time. No operational decisions occur before \(\tau_{\mathrm{obs}}\) except \(a\) itself.

## Construction

\[
\overline Q_{\mathrm{OTUB}}(a)=\mathbb E_\theta\big[r_{\mathrm{travel}}(a,\theta)+V_{\mathrm{post}}(x_a(\theta),S_a(\theta))\big]
\]

where \(S_a(\theta)\) is the posterior support after completing \(a\), and \(V_{\mathrm{post}}\) is an optimistic resource envelope that:

- if \(|S|=1\): counts \(r_C\) iff C is reachable by direct AC or AS→charge→SA→AC under that \(\theta\);
- if \(|S|>1\): counts \(r_C\) iff **one common route pattern** is reachable under **every** \(\theta\in S\) (nonanticipative information set).

Outside the `{A,C,S}` naming/family, the implementation returns `UNSUPPORTED_BOUND` (no silent prune).

## Proposition (family-restricted)

**Claim.** For every first corridor \(a\) in the declared model, \(Q^\star(a)\le \overline Q_{\mathrm{OTUB}}(a)\).

**Proof sketch.** The first-action term matches the exact travel reward in \(Q^\star\). Continuation rewards are at most \(r_A+r_C\) (energy costs are dropped → optimistic). Customer C appears in a nonanticipative optimum only if a common feasible pattern exists when \(|S|>1\), or a \(\theta\)-feasible pattern when Dirac; OTUB includes \(r_C\) whenever that reachability holds under the same physical SOC/time. Hence OTUB dominates \(Q^\star\).

## Relation to clairvoyant DRUB

**Goal (not automatic):** \(\overline Q_{\mathrm{OTUB}}(a)\le \overline Q_{\mathrm{DRUB}}(a)\).

On uninformative corridors, DRUB allows \(\theta\)-contingent open-loop continuations while OTUB forces a common C-pattern, so OTUB can be strictly tighter (verified on the baseline exploit action). On fully informative corridors with Dirac posteriors, OTUB and DRUB typically agree for this family.

## Novelty status

Observation-timing / nonanticipativity constraints are classical in stochastic optimization and dual control. OTUB as implemented is a **family-restricted engineering bound**, not a general EVRP theorem and not claimed as a fundamental new information-relaxation theory.

## Computational role

OTUB avoids known-\(\theta\) open-loop tree enumeration (uses reachability envelopes). On the preregistered suite it retains exact first actions but does **not** reduce total counted heavy operations below unpruned search (bound construction overhead).
