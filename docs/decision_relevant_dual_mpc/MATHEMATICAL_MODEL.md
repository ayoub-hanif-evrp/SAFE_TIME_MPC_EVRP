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
Observations only after completed travel. Inconsistency ⇒ fail-safe reject.

## Actions

Travel (named corridor segment), serve, charge_full, wait, accept/reject/defer.

## Causal safety

A first action is admissible only if for every \(\theta\) in the prior support there exists a continuation in the declared plan family completing \(\mathcal A_t\).  
Quantifier order: choose action from current info; continuations may use later observations; no dependence on unrealized \(\theta\) before it is learned.

## Objective

Expected delivery reward minus energy cost, subject to hard commitment safety. Reliability and reward reported separately in experiments.
