# Baseline-anchored predictive CC-E-MPC

**Controller class:** `BaselineAnchoredPredictiveCCE`  
**Module:** `src/safe_time_evrp/mpc_central/baseline_anchored_predictive_cce.py`

## Design

1. **Incumbent:** unchanged `CertificateCarryingEconomicMpc` with `scoring_mode="greedy_nominal"` (the strongest exploratory reference at SHA `442a423`).
2. **Fallback:** a validated incumbent action is always available before speculative scoring (anytime / cooperative deadline).
3. **Alternatives:** counterfactual generator (serve / accept / reject / charge / wait / reassignment) filtered by hard nominal feasibility.
4. **Forecast:** finite-demand / finite-active-period model (`mpc3c/finite_demand_forecast.py`), not homogeneous Poisson over the full horizon.
5. **Selection:** incumbent and alternatives scored with the **same causal objective** and **same scenarios**; override only if paired expected advantage exceeds a train-selected margin (`DEFAULT_IMPROVEMENT_MARGIN = 0.35`).
6. **Safety:** certificate / independent `validate_continuation` unchanged; no scenario-wise worst-regret floor.

## What this is not

- Not a guarantee of better realized service.
- Not hard real-time: ALNS calls are cooperatively budgeted, not preemptively interrupted.
- Not tuned on the final held-out evaluation seeds.

## Related

- Flexibility screening: `mpc_central/flexibility_features.py`
- Evaluation: `mpc_central/competitive_predictive_eval.py`
