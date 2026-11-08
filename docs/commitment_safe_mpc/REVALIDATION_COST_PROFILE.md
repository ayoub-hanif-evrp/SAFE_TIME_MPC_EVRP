# Computational bottleneck profile (repaired aggregation)

Artifact: `compute_bottleneck_profile.json`  
Command: `python -m safe_time_evrp.commitment_safe_mpc.compute_profile`

Totals are summed from **every decision audit** in the episode (not the last `decide()` only).

## Finding

- Outer B1/M1 continuation validation remains a tiny fraction of optimize time.  
- After repair, M1 ALNS reports `evaluate_route_calls ≈ 0` with large `full_calls_avoided` and measured suffix recompute counts.  
- Remaining cost is still dominated by the number of ALNS candidates / suffix propagations under the cooperative budget.
