# M1 ablation results (post-repair + Priority 7)

Artifacts:
- `baseline_comparison_m1_ablation.json`
- `compute_bottleneck_profile.json`
- `budget_frontier.json`

Commands:
```bash
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare --m1
python -m safe_time_evrp.commitment_safe_mpc.compute_profile
python -m safe_time_evrp.commitment_safe_mpc.budget_frontier
```

## Correctness

False-certificate and freight-prefix regressions green (`test_m1_correctness_repair.py`). Frontier smoke: `tests/test_budget_frontier.py`.

## Episode-aggregated compute profile (9 development cases)

| Metric | Approx. mean |
|--------|----------------|
| B1 optimize seconds | ~0.165 |
| M1 optimize seconds | ~0.156 |
| M1 `evaluate_route_calls` (ALNS hot path) | **0** |
| M1 `full_calls_avoided` | ~1681 |
| M1 suffix visits recomputed | ~4760 |

## Fixed-budget frontier (10–50 cust)

See `COMPUTATION_SERVICE_FRONTIER.md`. Controllers: insertion / b0 / b1 / m1 / m1_no_reuse / m1_full_eval / m1_both_off. Headline: M1 faster on 13/15 cells vs B1; more completed on 2/15 only — no operational dominance claim.

