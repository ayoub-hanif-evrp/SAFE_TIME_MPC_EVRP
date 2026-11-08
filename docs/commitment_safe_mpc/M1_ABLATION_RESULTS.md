# M1 ablation results

Artifact: `baseline_comparison_m1_ablation.json`  
Command: `python -m safe_time_evrp.commitment_safe_mpc.baseline_compare --m1`

## Controllers

| Key | Meaning |
|-----|---------|
| insertion | Constructive MPC |
| alns / b1 | B0 / B1 |
| m1 | Incremental eval + certificate reuse |
| m1_no_reuse | Incremental eval, no cross-event reuse |
| m1_full_eval | Full eval + certificate reuse |

## Reading the results

Compare completed counts, executed distance, optimize seconds, and validation seconds under matched budgets. Do not claim success from fewer route-evaluation counters alone — the paper-relevant question is better executable service/cost at fixed compute.

See JSON for numbers; regenerate after code changes.
