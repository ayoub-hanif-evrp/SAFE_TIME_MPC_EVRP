# Frontier `accepted_unfulfilled` audit (Task 5)

Source: `docs/commitment_safe_mpc/budget_frontier.json` (31 rows with AU>0).  
Replay module: `mpc_central/fulfillment_audit.py` → `fulfillment_audit.json`.

## Method

Re-run each (case, controller, budget, seed) on `FleetSimulator` via `run_episode`, then label from **observed** end state:

| Label | Meaning |
|-------|---------|
| `tmax_censor_busy_fleet` | end_time ≥ t_max and fleet not idle at depot |
| `tmax_censor_accepted_remaining` | end_time ≥ t_max with residual accepts |
| `no_feasible_continuation_with_residual_accepts` | AU present and episode recorded `no_feasible_continuation` decisions |
| `residual_accepts_before_natural_end` | AU without the above |
| `no_accepted_unfulfilled` | AU did **not** reproduce on re-run |

`replay_ok` is recorded separately and is **not** fulfillment.

## Results (31 re-runs)

| Label | Count |
|-------|------:|
| `no_feasible_continuation_with_residual_accepts` | 17 |
| `no_accepted_unfulfilled` | 14 |

No row in this re-run was classified as pure `tmax_censor_*`.

## Reading

1. When AU reproduces, it co-occurs with `no_feasible_continuation_count > 0` — i.e. controllers sometimes accept under plans that later lose a certified continuation, leaving residual accepts at episode end.  
2. 14/31 AU rows **did not reproduce** under the same seed/budget — cooperative `time_limit_seconds` wall-clock search is not bit-stable across machines/loads. Treat original frontier AU counts as noisy.  
3. Still: **do not equate `replay_ok` with commitment fulfillment.**
