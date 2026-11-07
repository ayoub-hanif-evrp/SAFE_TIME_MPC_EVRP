# Mathematical model — Decision-relevant dual MPC

Branch: `research/decision-relevant-dual-mpc`  
Package: `src/safe_time_evrp/dr_dual/`

## State

\[
s_t=(x_t,\mathcal A_t,b_t)
\]

- \(x_t\): fleet node, time, SOC, load, busy_until (noninterruptible).
- \(\mathcal A_t\): accepted commitments.
- \(b_t\): finite-support Bayesian belief on shared latent energy factor \(\theta\).

## Energy

Segment \(a\): \(e_a=\phi_0(a)+\phi_1(a)\theta^\star+\varepsilon\).  
Observations only after completed travel at time \(\tau_{\mathrm{obs}}\). Inconsistency ⇒ fail-safe reject.

## Actions

Travel (named corridor segment), serve, charge_full, wait, accept/reject.

## Causal safety / nonanticipativity

\[
h_t(\theta_1)=h_t(\theta_2)\implies \pi(h_t(\theta_1))=\pi(h_t(\theta_2)).
\]

Decisions before \(\tau_{\mathrm{obs}}\) cannot depend on the unrealized observation. After \(\tau_{\mathrm{obs}}\), recourse may use the posterior.

## Objective

Expected delivery reward minus energy cost, subject to hard commitment completion (\(\mathcal A\subseteq\) completed).

## Exact reference scope

`EXACT_OPTIMUM` = optimum within an explicitly documented finite policy class (single-EV corridor family or history-indexed two-EV `{DIRECT,CHARGE,SKIP}`), not a continuous general EVRP optimum.

## Fleet VoI isolation

Hold EV1’s physical first action fixed; compare EV2 optimized causal value with vs without receiving EV1’s completed energy observation (`fleet_voi.py`). Label changes without \(\Delta>0\) are not information value.
