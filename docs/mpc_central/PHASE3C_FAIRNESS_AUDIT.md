# Phase 3C — Fairness audit (matched evaluation budgets)

**Branch tip at authorship:** post-`fd366b4` Phase 3C work  
**Verdict: REVISE**

## Defects repaired

| Defect | Fix |
|--------|-----|
| Uniform re-evaluated plant outcomes without charging budget | `EvalBank` caches `(action, scenario)`; only first compute increments `n_evals` |
| Adaptive called `exhaustive_action_values()` online | Removed; adaptive uses bank samples only (`no_oracle_in_loop`) |
| Reported budget ≠ actual rollouts | Assert `actual_evals <= budget` on every policy result |
| Candidate-order artifact at budget 3 | Explicit reverse/permutation stress; wins that vanish are listed in `fragile_notes` |

## Fairness suite summary (`phase3c_results.json`)

| Metric | Value |
|--------|------:|
| Comparisons (base + order/scenario stress) | 27 |
| Adaptive better than uniform | 3 |
| Uniform better than adaptive | 0 |
| Ties | 24 |
| Fragile notes | 3 (all budget=3 wins vanish under reversed candidate order) |

**Interpretation:** Under *honest* budgets, adaptive still wins a few original-order budget-3 cells, but those wins are **order-dependent**. That is not a trustworthy MPC-specific mechanism.

## Stop / next

Do **not** scale Phase 4 on this evidence. Revise the allocation rule (or the scientific claim) so any advantage survives candidate/scenario order permutations and stronger baselines (random allocation is included in the suite rows).
