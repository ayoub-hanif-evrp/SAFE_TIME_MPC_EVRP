# Formal multistage model (Gate 3A discrete reference)

This document defines the **discretized** mathematical model used by the exact oracle. Continuous Schneider physics is not claimed by implication.

## Objects

1. **Plant state** \(x\): time, node (or in-progress arc), SOC, onboard load, locked noninterruptible action, set of remaining accepted customers, residual uncertainty budget \(\Gamma_{\mathrm{rem}}\).
2. **Information state** \(y\): plant fields observable at a decision epoch; no hidden future requests; no future disturbance realizations.
3. **Plan / policy**: a causal map from information histories to legal actions (next node, and if at a charger, charge increment).

## Actions

At an idle node \(i\):

- Travel toward a neighbor \(j\) (starts a noninterruptible arc).
- If \(i\) is a charger: choose charge increment \(\Delta q \in \{0,1,\ldots,Q-q\}\) with duration \(g\cdot\Delta q\), then SOC becomes \(\min(Q,q+\Delta q)\).
- If all commitments are done and \(i\) is the depot: terminate.

Charge increments are chosen **only** from the SOC observed at the station. Future SOC is not available earlier.

## Disturbances

Each travel arc has a finite set of realizations \(w\in\mathcal W_{ij}\) affecting travel time and energy. A budgeted model uses binary (or integer) deviation counts:

\[
\sum_{\text{realized arcs }a} z_a \le \Gamma,\qquad z_a\in\{0,1\}.
\]

After observing a deviation of size \(z\) on an arc, the residual budget updates as

\[
\Gamma_{\mathrm{rem}} \leftarrow \Gamma_{\mathrm{rem}} - z.
\]

Illegal full reset \(\Gamma_{\mathrm{rem}}\leftarrow\Gamma\) at every replan is a different uncertainty contract and must not be silently used.

Budgets are attached to **physical transitions**, not to “number of arcs on a speculative route” in a way that lets the controller manufacture budget by rewriting unexecuted plans after the fact. For the tiny oracle, the stage count is the sequence of executed travels.

## Quantifiers

**Open-loop robustness.** There exists a fixed action sequence \(u_{0:T}\) such that for every admissible disturbance path the commitments are met.

**Feedback (causal) robustness.** There exists a policy \(\pi\) such that for every admissible disturbance path, actions depend only on the observed history, and commitments are met.

**Two-stage adjustable (Han-style simplification).** A first-stage route (node sequence) is fixed; wait-and-see variables (charge amounts) may depend on the **full** disturbance realization on that route. This is **not** allowed to change the customer order after seeing a prefix of disturbances.

**Clairvoyant.** The entire disturbance path is known before any decision. Upper bound only.

## Viability

\[
x\in\mathcal V
\iff
\exists\,u\ \forall\,w\in\mathcal W(x):
f(x,u,w)\in\mathcal V
\]

with \(\mathcal W(x)\) the residual-budget-feasible disturbances, and terminal states those with all accepted customers served and vehicle at depot with SOC/time feasible.

## Commitments

Accepted customers must be served within their windows under every admissible disturbance path consistent with residual budget. Announced but unaccepted customers are not obligations. Hidden future requests are not in \(y\).
