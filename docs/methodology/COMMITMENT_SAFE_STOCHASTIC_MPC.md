# Commitment-Safe Stochastic MPC — formulation

**Proposed method (single controller):** `CommitmentSafeStochasticMpc`  
**Baselines (preserved, not proliferated):** B1, M1, greedy-nominal CC-E-MPC, existing stochastic / causal CC-E predictive MPC.

Historical CC-E-MPC note: `FINAL_MPC_FORMULATION.md` (certificate-carrying economic ranking). This document is the **paper formulation** target.

Objective weights are the plant constants and stay fixed in controlled comparisons:

- `SERVICE_REWARD = 100`
- `UNFULFILLED_PENALTY = 250`
- `DISTANCE_PENALTY = 1`
- Charging cost enters through time/distance proxies already reflected in executed distance and opportunity cost inside rollouts (no silent retuning).

---

## 1. MPC state \(x_t\)

- EV positions, status, locked destinations, anchors (noninterruptible travel/service/charge).
- SoC and battery capacity; load and onboard customers.
- Accepted commitments \(A_t\); announced undecided \(U_t\); completed / rejected / deferred / in-service.
- Service and charging time windows on public nodes.
- Clock \(t\) and public information only (`make_public_snapshot`).

## 2. Decisions \(u_t\)

- Accept / reject newly announced customers.
- Vehicle–customer assignment and service sequencing (route plan).
- Charging-station choices and charge quantities/durations (via charge visits).
- Waiting / repositioning where the plant permits.
- **Executed:** only the first physical action of the plan; tails are informational until the next re-solve.

## 3. Finite-horizon stochastic problem

\[
\max_{\pi}
\mathbb{E}\Bigl[
\sum_{\tau=t}^{t+H}
\bigl(
R_{\mathrm{svc}}\,n^{\mathrm{svc}}_\tau
- c_{\mathrm{travel}}\,d_\tau
- c_{\mathrm{charge}}\,q_\tau
- P_{\mathrm{AU}}\,n^{\mathrm{AU}}_\tau
\bigr)
+ V_f(x_{t+H},A_{t+H})
\Bigr]
\]

subject to, for every scenario \(s\):

1. **Dynamics** under nominal EV physics and scenario request revelations after their announcement times.
2. **Nonanticipativity:** decisions at stage \(k\) depend only on information available at \(t+k\) (shared first action across scenarios).
3. **Hard commitment:** \(A_t \cup A^{\mathrm{new}}_t\) covered by a validated continuation at stage 0.
4. **Locks:** noninterruptible actions cannot be preempted.
5. **Terminal:** \((x_{t+H}^{(s)}, A_{t+H}^{(s)}) \in \mathcal{X}_f\) or a certified feasible suffix is attached.
6. **Information:** no dependence on unreleased attributes.

Soft economic penalties ≠ hard feasibility.

## 4. Receding-horizon execution

1. Solve (approximately) the problem at \(t\).
2. Apply stage-0 action.
3. At the next event, observe public state; warm-start from the previous certificate / plan suffix; re-solve.

This loop is mandatory in code, tests, and manuscript.

## 5. Practical solver (PoC)

Exact multi-stage stochastic MIP is intractable online. The PoC approximation:

1. Keep a verified incumbent certificate (warm start).
2. Generate commitment-feasible first-action candidates (ALNS + heuristics) under the public snapshot.
3. Score with shared finite-demand scenarios and causal B1-validated recourse implementing the economic objective.
4. Enforce terminal coverage via independent `validate_continuation` before accept.
5. Stop on cooperative wall; emit incumbent. Profile every decide().

ALNS is an **internal subroutine**, not the scientific object.

## 6. Ablations (development only, after tests)

| Experiment | Question |
|---|---|
| Nominal vs stochastic scenarios | Uncertainty modeling |
| With/without terminal commitment constraint | Recursive feasibility value |
| With/without predictive charging candidates | Energy anticipation |
| Short vs longer \(H\) | Lookahead value |
| With/without warm starts | Runtime practicality |
| Normal vs consistently relaxed battery | EV-specificity |

No confirmatory run until development + correctness gates pass.
