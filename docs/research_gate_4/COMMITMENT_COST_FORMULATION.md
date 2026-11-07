# Gate 4 — Commitment-Cost MPC Formulation

## Finite-horizon causal control

State \(x\): fleet locations, SOC, payload, locked transitions.  
Accepted set \(\mathcal A\): irreversible service promises.  
Announced unaccepted \(\mathcal R\); anonymous future scenarios \(\xi\).

Causal policies \(\pi\in\Pi_{\mathrm{causal}}\) map observable history to executable routing/charging actions under noninterruptible physical transitions and finite decision deadlines.

## Value and marginal cost

\[
V_H(x,\mathcal A)
=
\sup_{\pi\in\Pi_{\mathrm{causal}}}
\mathbb E\!\left[R_H(\pi)-\lambda C_H(\pi)\right]
\quad\text{s.t. commitment feasibility for }\mathcal A.
\]

For newly announced \(r\):
\[
\Delta_r(x,\mathcal A)=V_H(x,\mathcal A)-V_H(x,\mathcal A\cup\{r\}).
\]

This is standard marginal-value reasoning (cf. Zhang et al. opportunity-cost ADP), **not** a new theorem.

## Objective clarification (this gate)

Primary toy oracle objective: **expected completed customers** under commitment feasibility for \(\mathcal A\).  
Operational cost \(C_H\) enters only as a secondary tie-break in constructive planners.

Hard separation:

- **Robust / nominal feasibility** for accepted \(\mathcal A\) (plant commitment gate).
- **Probabilistic service** for unaccepted future demand (scenario expectations).

No large arbitrary weighted sum concealing hard feasibility.

## Uncertainty set (documented)

Gate 3E/4 controllers remain **single-scenario anticipatory** when using anonymous forecasts — not scenario-tree stochastic MPC unless explicitly stated.
