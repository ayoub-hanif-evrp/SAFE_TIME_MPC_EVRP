# Gate 3C — Flexibility-aware MPC mechanism

## Objective

At each decision epoch, build a finite-horizon fleet plan and score candidates by

\[
J = -(\mathrm{distance} + 0.1\cdot\mathrm{charge\_time}) + \lambda \sum_v F(s_v)
\]

with \(\lambda=0.75\) and terminal flexibility

\[
F(s) = w_{\mathrm{soc}}\frac{\mathrm{SOC}}{Q} + w_{\mathrm{chg}}\#\{\text{reachable chargers}\} + w_{\mathrm{ins}}\#\{\text{feasible next insertions}\} - w_{\mathrm{rem}}|\mathcal{R}|.
\]

Implemented in [`mpc3c/flexibility.py`](../../src/safe_time_evrp/mpc3c/flexibility.py) and [`mpc3c/controllers.py`](../../src/safe_time_evrp/mpc3c/controllers.py).

## Horizon

`horizon` is passed into `construct_routes` for RH, rollout, and flexibility controllers (customers with `ready > now+horizon` are deferred). Myopic uses ready-only customers. This is a **real** horizon, unlike legacy `anytime.improve`.

## Nonanticipativity

Decisions use only `Observation` fields (released/accepted/completed). Future ready times beyond the horizon are deferred, not planned as known services.

## Compute budget

Matched across rollout and flexibility: up to 8 prefix customer pins per epoch.

## Baselines

| Name | Role |
| --- | --- |
| myopic | Ready-only insertion |
| rh_open_loop | Horizon insertion, distance score |
| rollout | PI prefix search, distance score |
| flexibility_mpc | Same candidate set as rollout, score += λF |

## What is not claimed

- Not a new viability theorem / Bellman certificate.
- Not Case-P rectangle certification of partial targets.
- Not road-network optimality.
