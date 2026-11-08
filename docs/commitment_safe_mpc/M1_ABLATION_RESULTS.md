# M1 ablation results (post-repair)

Artifacts:
- `baseline_comparison_m1_ablation.json`
- `compute_bottleneck_profile.json`

Commands:
```bash
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare --m1
python -m safe_time_evrp.commitment_safe_mpc.compute_profile
```

## Correctness

False-certificate and freight-prefix regressions green (`tests/test_m1_correctness_repair.py`).

## Episode-aggregated compute profile (9 development cases)

| Metric | Approx. mean |
|--------|----------------|
| B1 optimize seconds | ~0.165 |
| M1 optimize seconds | ~0.156 |
| M1 `evaluate_route_calls` (ALNS hot path) | **0** |
| M1 `full_calls_avoided` | ~1681 |
| M1 suffix visits recomputed | ~4760 |

M1 is no longer a fake incremental wrapper: the ALNS hot path uses suffix propagation. On this suite, mean wall time is slightly below B1; completed customers remain matched on the five tiny cases (no automatic service win).

## Controllers

insertion / alns / b1 / m1 / m1_no_reuse / m1_full_eval — see JSON for per-case executed distance and completed sets.
