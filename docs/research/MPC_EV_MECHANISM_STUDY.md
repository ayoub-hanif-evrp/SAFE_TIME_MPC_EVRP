# EV-specific mechanism study — energy-gated anticipatory charging

## Motivation (from decision-quality diagnosis)

On `r103C10` / `rc108C10` / `rc108C15`, CSS diverged from greedy-nominal at \(t=0\) by
selecting **charge** while GN **served** the announced customer. Closed-loop economic
deltas were large and negative (−900 to −1400 on those cells). Forecast vs empty rankings
often agreed; the failure was **charge preference under weak value separation**, not a
missing forecast.

## Mechanism

Let \(u^\star\) be the ranked winner and \(u^{\mathrm{svc}}\) the best non-charge alternative
in the same feasibility class. If \(u^\star\) is anticipatory charge (incumbent not charging):

\[
\text{select }u^{\mathrm{svc}}\text{ if } \hat J(u^\star)-\hat J(u^{\mathrm{svc}}) < \eta,
\]

with \(\eta=25\) in development (same units as the economic score). If the advantage clears
\(\eta\), charge is kept — i.e. predictive charging remains available when its estimated
value is material relative to delayed service.

Ablation: `css_mpc_no_energy_gate` disables the gate (prior ranking behavior).

## Predeclared regimes (report all cells)

Development comparison reports energy-gate on/off under the standard Schneider medium
dynamicity battery model. Infinite-battery cells remain a small consistency check only.

## Claim discipline

A credible EV claim requires that advantage arise from energy/charging dynamics.
This gate is necessary for scientific honesty about anticipatory charge; whether it yields
a **reliable** economic win vs greedy-nominal is answered only by the development comparison.
