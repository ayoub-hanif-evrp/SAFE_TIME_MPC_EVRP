# Phase 3C — Fairness audit (matched evaluation budgets)

**Branch tip at authorship:** `bf8838d` Phase 3C work  
**Verdict: REVISE**

> **Phase 3D note:** Numbers below match the committed `phase3c_results.json` written by
> `tests/test_mpc_central_phase3c.py` with `budgets=(3, 4)` → **18** comparisons / **15** ties.
> An earlier draft of this document incorrectly stated 27 / 24 (that would be
> `budgets=(3, 4, 6)`). Reconciled 12 November 2026.

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
| Comparisons (base + order/scenario stress) | 18 |
| Adaptive better than uniform | 3 |
| Uniform better than adaptive | 0 |
| Ties | 15 |
| Fragile notes | 3 (all budget=3 wins vanish under reversed candidate order) |

**Interpretation:** Under *honest* budgets, adaptive still wins a few original-order budget-3 cells, but those wins are **order-dependent**. That is not a trustworthy MPC-specific mechanism.

## Stop / next

Do **not** scale Phase 4 on this evidence. Phase 3D repairs the evaluation contract
(distance, B1 recourse, estimation) and introduces a minimal closed-loop predictive
MPC controller compared against B1 / equal allocation / paired CRN — not another
hand-designed adaptive-sampler paper claim.
