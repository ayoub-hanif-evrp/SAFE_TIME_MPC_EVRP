# Conditional (decision-epoch) anonymous forecast model

**Purpose:** Supply future-demand scenarios to CC-E-MPC / stochastic MPC without the
static catalogue that expired after absolute time 200.

## Information boundary

- Spatial/service atoms are fit on **training Schneider instances only**.
- Announcement rate μ is calibrated from **training release histories only**
  (Schneider-derived protocol v2).
- Forecast customers are anonymous (`syn_cond_*` / `syn_crn_*`).
- Evaluation-customer IDs, coordinates, windows, and true future releases are
  **never** injected into online `decide()`.

## Sampling at decision time `t`

For each scenario index `s` and planning horizon `H`:

1. Seed an LCG from `(policy_seed, s, time_bucket=round(10t), μ, model_id)`.
2. Draw successive exponential gaps with mean μ.
3. Keep arrivals with times in `(t, t+H]`.
4. Assign spatial attributes by sampling train atoms with small jitter.
5. Stop when the next draw would exceed `t+H`, or at a hard cap (default 32).

Empty scenarios are valid when the Poisson process yields no events in the remaining window.

## Common-random-number (CRN) μ comparisons

`sample_conditional_scenarios_crn` draws shared uniforms once per scenario, then
applies `gap = −μ log(1−u)` for each candidate μ. Forecasts compared under CRN
differ in **rate parameters**, not independent unrelated samples.

## Scoring consistency

Forecast-on and forecast-off (causal empty-future) both use `rollout_candidate`
via `expected_rollout_value(..., scoring_mode="causal")`.

The legacy `100 × served − distance` heuristic is preserved only as
`scoring_mode="greedy_nominal"` / controller name `cce_greedy_nominal`.

## Implementation

- [`src/safe_time_evrp/mpc3c/forecast.py`](../../src/safe_time_evrp/mpc3c/forecast.py) — `sample_conditional_scenarios`, CRN helper
- [`src/safe_time_evrp/mpc_central/cce_mpc.py`](../../src/safe_time_evrp/mpc_central/cce_mpc.py) — `conditional_forecast=True`
- [`src/safe_time_evrp/mpc_central/scenario_rollout.py`](../../src/safe_time_evrp/mpc_central/scenario_rollout.py) — unified causal scoring
