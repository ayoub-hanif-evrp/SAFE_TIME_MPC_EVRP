# Baseline comparison (tiny development instances)

```bash
python -c "from safe_time_evrp.dr_dual.experiments import write_artifacts; from pathlib import Path; write_artifacts(Path('docs/decision_relevant_dual_mpc'))"
```

Artifact: `docs/decision_relevant_dual_mpc/small_instance_results.json`

## Method definitions (must not share valuation)

| Method | Selection criterion | Posterior use |
|--------|---------------------|---------------|
| Exact dual MPC | Bayes value with nonanticipative continuations | Yes, after observation |
| DR pruning MPC | Same as dual; prune by UB ≤ verified L | Yes |
| Robust MPC | Worst-case common plan under **forced prior** | No exploitation |
| Optimized passive | Expected reward with **forced prior** continuation (ordinary travel still physically observes energy) | Not used for selection |
| Info-gain heuristic | Max \|φ₁\| among safe first actions | N/A (heuristic) |

Each baseline reports `selection_score` (what it optimized) and `true_bayes_value` of the chosen first action (common decision-quality metric).

## Reconciliation with `solve_exact_single`

Optimized passive first action must match `extras["passive_optimized_first"]`. Exact dual first action is the Bayes optimum. On the primary toy, dual selects **inform**; passive selects **exploit**.

## Fair compute ablation

`solve_dr_dual(use_pruning=False)` evaluates **no** upper bounds. Compare counters (`bound_evaluations`, `resource_bound_evaluations`, continuation calls) and repeated timings across ≥2 networks. Do not infer scalability from one pruned decoy corridor.

## What this does / does not support

- **Supports:** dual ≠ passive on the toy; pruning can retain the dual first action while skipping a dominated decoy under DRUB.
- **Does not support:** dual outperforming robust/info-gain when those methods also select inform on the same toy; large-scale runtime claims.
